// Live API client for backend communication with Server-Sent Events support
import { ProcessingStatus } from '../types';

// API endpoints for live mode
const LIVE_API_BASE_URL = 'https://gimme-ai-test.erniesg.workers.dev';

export const LIVE_API_ENDPOINTS = {
  START_GENERATION: `${LIVE_API_BASE_URL}/generate_video_stream`,
  JOB_STATUS: `${LIVE_API_BASE_URL}/job_status`,
  GET_VIDEO: `${LIVE_API_BASE_URL}/get_video`,
  CLEANUP: `${LIVE_API_BASE_URL}/cleanup`,
  VIDEOS: `${LIVE_API_BASE_URL}/videos`
};

// Server-Sent Events (SSE) connection for log streaming
export const createLogWebSocket = (jobId: string, onMessage: (log: string) => void, onError: (error: any) => void, onComplete: () => void) => {
  try {
    const sseUrl = `${LIVE_API_BASE_URL}/stream_logs/${jobId}`;
    console.log(`[LiveAPI] Connecting to SSE stream: ${sseUrl}`);

    const eventSource = new EventSource(sseUrl);

    eventSource.onopen = () => {
      console.log('[LiveAPI] SSE connection established');
    };

    eventSource.onmessage = (event) => {
      try {
        console.log('[LiveAPI] SSE message received:', event.data);
        const data = JSON.parse(event.data);

        if (data.message) {
          // Handle message format from backend
          onMessage(data.message);

          // Check for completion message
          if (data.message.includes('Video generation complete')) {
            console.log('[LiveAPI] Generation complete from message');
            // Don't close the connection yet, wait for the status:complete message
          }
        } else if (data.log) {
          // Handle alternative log format
          onMessage(data.log);

          // Check for special log messages
          if (data.log.startsWith('DONE:') || data.log.includes('Video generation complete')) {
            console.log('[LiveAPI] Generation complete');
            // Don't close the connection yet, wait for the status:complete message
          } else if (data.log.startsWith('ERROR:')) {
            console.error('[LiveAPI] Error:', data.log.substring(6));
            onError(new Error(data.log.substring(6)));
          }
        } else if (data.status === 'complete' && data.video_path) {
          // Direct completion message
          console.log('[LiveAPI] Generation complete with video path:', data.video_path);
          onMessage(`Video generation complete: ${data.video_path.split('/').pop()}`);
          onComplete();
          eventSource.close();
        }
      } catch (error) {
        console.error('[LiveAPI] Error parsing SSE message:', error);
        onMessage(event.data);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[LiveAPI] SSE error:', error);
      onError(error);
      eventSource.close();
    };

    return {
      close: () => {
        eventSource.close();
      }
    };
  } catch (error) {
    console.error('[LiveAPI] Error creating SSE connection:', error);
    onError(error);
    return {
      close: () => {}
    };
  }
};

// Error handling wrapper
const handleApiResponse = async (response: Response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `API error: ${response.status}`);
  }
  return response;
};

// Live API client functions
export const liveApiClient = {
  // Start video generation process
  startGeneration: async (content: string): Promise<{ job_id: string, status: string }> => {
    try {
      console.log('[LiveAPI] Starting generation with content:', content.substring(0, 100) + '...');

      const response = await fetch(LIVE_API_ENDPOINTS.START_GENERATION, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      });

      const processedResponse = await handleApiResponse(response);
      return await processedResponse.json();
    } catch (error) {
      console.error('[LiveAPI] Error starting generation:', error);
      throw error;
    }
  },

  // Check job status
  checkJobStatus: async (jobId: string): Promise<{ status: string, progress?: number, message?: string, logs?: string[], video_path?: string }> => {
    try {
      console.log(`[LiveAPI] Checking job status for: ${jobId}`);

      const response = await fetch(`${LIVE_API_ENDPOINTS.JOB_STATUS}/${jobId}`);
      const processedResponse = await handleApiResponse(response);
      return await processedResponse.json();
    } catch (error) {
      console.error('[LiveAPI] Error checking job status:', error);
      throw error;
    }
  },

  // Get generated video
  getVideo: async (jobId: string): Promise<Blob | string> => {
    try {
      console.log(`[LiveAPI] Getting video for job: ${jobId}`);

      // First check job status to get the video path
      const status = await liveApiClient.checkJobStatus(jobId);

      if (status.status !== 'complete') {
        throw new Error('Video generation not complete yet');
      }

      if (status.video_path) {
        console.log(`[LiveAPI] Video path from status: ${status.video_path}`);

        // Extract the filename from the path
        const videoFileName = status.video_path.split('/').pop();
        if (videoFileName) {
          // Try to access the video directly from the backend
          try {
            // First try the videos endpoint
            const directVideoUrl = `${LIVE_API_ENDPOINTS.VIDEOS}/${videoFileName}`;
            console.log(`[LiveAPI] Trying direct video URL: ${directVideoUrl}`);

            // Test if the URL is accessible
            const testResponse = await fetch(directVideoUrl, { method: 'HEAD' });
            if (testResponse.ok) {
              console.log(`[LiveAPI] Direct video URL is accessible`);
              return directVideoUrl;
            }
          } catch (error) {
            console.log(`[LiveAPI] Direct video URL not accessible, falling back to get_video endpoint`);
          }
        }
      }

      // Fallback to the get_video endpoint
      const response = await fetch(`${LIVE_API_ENDPOINTS.GET_VIDEO}/${jobId}`);

      // Check if response is OK
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      // Check content type to determine how to handle the response
      const contentType = response.headers.get('content-type');
      console.log(`[LiveAPI] Video response content type: ${contentType}`);

      if (contentType && contentType.includes('application/json')) {
        // Handle JSON response (might contain a URL or error)
        const data = await response.json();
        if (data.url) {
          return data.url; // Return the URL as a string
        } else if (data.error) {
          throw new Error(data.error);
        } else {
          throw new Error('Invalid JSON response from video endpoint');
        }
      } else if (contentType && contentType.includes('video/')) {
        // Handle binary response (video file)
        console.log('[LiveAPI] Received video file, creating blob');
        return await response.blob();
      } else {
        // Unknown content type, try to get as blob anyway
        console.log('[LiveAPI] Unknown content type, trying as blob');
        return await response.blob();
      }
    } catch (error) {
      console.error('[LiveAPI] Error getting video:', error);
      throw error;
    }
  },

  // Cleanup job resources
  cleanup: async (jobId: string): Promise<void> => {
    try {
      console.log(`[LiveAPI] Cleaning up job: ${jobId}`);

      await fetch(`${LIVE_API_ENDPOINTS.CLEANUP}/${jobId}`, {
        method: 'DELETE',
      }).catch(err => {
        // Ignore 404 errors for cleanup
        if (err.message && err.message.includes('404')) {
          console.log('[LiveAPI] Cleanup endpoint not found (404), this is expected if the backend does not implement cleanup');
        } else {
          throw err;
        }
      });
    } catch (error) {
      console.error('[LiveAPI] Error cleaning up job:', error);
      // Non-critical error, so we don't throw
    }
  },

  // Mock functions for testing without actual backend
  mock: {
    startGeneration: async (content: string): Promise<{ job_id: string, status: string }> => {
      console.log('[LiveAPI Mock] Starting generation with content:', content.substring(0, 100) + '...');

      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));

      return {
        job_id: `mock-${Date.now()}`,
        status: 'processing'
      };
    },

    simulateLogMessages: (onMessage: (log: string) => void, onComplete: () => void) => {
      const logs = [
        "Initializing AI video generation pipeline...",
        "Loading content analysis module...",
        "Analyzing text structure...",
        "Extracting key themes and topics...",
        "Generating scene concepts...",
        "Creating visual storyboard...",
        "Initializing video generation model...",
        "Rendering scene 1 of 3...",
        "Applying style transfer to scene 1...",
        "Rendering scene 2 of 3...",
        "Applying style transfer to scene 2...",
        "Rendering scene 3 of 3...",
        "Applying style transfer to scene 3...",
        "Generating audio track...",
        "Synchronizing audio with visuals...",
        "Applying final post-processing effects...",
        "Optimizing for TikTok format...",
        "Encoding final video...",
        "Video generation complete!"
      ];

      let index = 0;
      const interval = setInterval(() => {
        if (index < logs.length) {
          onMessage(logs[index]);

          if (logs[index].startsWith('Video generation complete')) {
            clearInterval(interval);
            onComplete();
          }

          index++;
        } else {
          clearInterval(interval);
          onComplete();
        }
      }, 1000);

      return {
        stop: () => clearInterval(interval)
      };
    },

    getVideo: async (): Promise<string> => {
      console.log('[LiveAPI Mock] Getting mock video');

      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));

      return "https://github.com/erniesg/wanx/raw/refs/heads/main/backend/assets/demo/output.mp4";
    }
  }
};

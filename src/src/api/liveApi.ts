// Live API client for backend communication with WebSocket support
import { ProcessingStatus } from '../types';

// API endpoints for live mode
const LIVE_API_BASE_URL = 'https://api.wanx.io';

export const LIVE_API_ENDPOINTS = {
  START_GENERATION: `${LIVE_API_BASE_URL}/generate_video`,
  JOB_STATUS: `${LIVE_API_BASE_URL}/job_status`,
  GET_VIDEO: `${LIVE_API_BASE_URL}/video`,
  CLEANUP: `${LIVE_API_BASE_URL}/cleanup`,
};

// WebSocket connection for log streaming
export const createLogWebSocket = (jobId: string, onMessage: (log: string) => void, onError: (error: any) => void, onComplete: () => void) => {
  try {
    const wsUrl = `ws://${LIVE_API_BASE_URL.replace('https://', '')}/ws/logs/${jobId}`;
    console.log(`[LiveAPI] Connecting to WebSocket: ${wsUrl}`);
    
    const socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
      console.log('[LiveAPI] WebSocket connection established');
    };
    
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.log) {
          // Check for special log messages
          if (data.log.startsWith('DONE:')) {
            console.log('[LiveAPI] Generation complete');
            onComplete();
          } else if (data.log.startsWith('ERROR:')) {
            console.error('[LiveAPI] Error:', data.log.substring(6));
            onError(new Error(data.log.substring(6)));
          } else {
            onMessage(data.log);
          }
        }
      } catch (error) {
        console.error('[LiveAPI] Error parsing WebSocket message:', error);
        onMessage(event.data);
      }
    };
    
    socket.onerror = (error) => {
      console.error('[LiveAPI] WebSocket error:', error);
      onError(error);
    };
    
    socket.onclose = () => {
      console.log('[LiveAPI] WebSocket connection closed');
    };
    
    return {
      close: () => {
        socket.close();
      }
    };
  } catch (error) {
    console.error('[LiveAPI] Error creating WebSocket:', error);
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
  checkJobStatus: async (jobId: string): Promise<{ status: string, progress?: number, message?: string }> => {
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
  getVideo: async (jobId: string): Promise<Blob> => {
    try {
      console.log(`[LiveAPI] Getting video for job: ${jobId}`);
      
      const response = await fetch(`${LIVE_API_ENDPOINTS.GET_VIDEO}/${jobId}`);
      const processedResponse = await handleApiResponse(response);
      return await processedResponse.blob();
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
        "Analyzing text structure and semantics...",
        "Extracting key themes and topics...",
        "Generating scene concepts based on content...",
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
        "DONE: Video generation complete!"
      ];
      
      let index = 0;
      const interval = setInterval(() => {
        if (index < logs.length) {
          onMessage(logs[index]);
          
          if (logs[index].startsWith('DONE:')) {
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
import { useState, useCallback, useEffect, useRef } from 'react';
import { useAppStore } from '../store';
import { liveApiClient, createLogWebSocket } from '../api/liveApi';

export const useLiveVideoGeneration = () => {
  const { 
    setCurrentPage, 
    inputValue, 
    setProcessingStatus,
    isLiveMode,
    currentPage
  } = useAppStore();
  
  const [jobId, setJobId] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);
  
  const webSocketRef = useRef<{ close: () => void } | null>(null);
  const logSimulatorRef = useRef<{ stop: () => void } | null>(null);
  const statusPollingRef = useRef<NodeJS.Timeout | null>(null);
  
  // Cleanup function
  const cleanup = useCallback(() => {
    // Close WebSocket if open
    if (webSocketRef.current) {
      webSocketRef.current.close();
      webSocketRef.current = null;
    }
    
    // Stop log simulator if running
    if (logSimulatorRef.current) {
      logSimulatorRef.current.stop();
      logSimulatorRef.current = null;
    }
    
    // Clear status polling interval
    if (statusPollingRef.current) {
      clearInterval(statusPollingRef.current);
      statusPollingRef.current = null;
    }
  }, []);
  
  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);
  
  // Update processing status
  const updateStatus = useCallback((
    progress: number, 
    message: string, 
    step: 'analyzing' | 'generating' | 'rendering' | 'complete'
  ) => {
    setProcessingStatus({
      step,
      progress,
      message
    });
  }, [setProcessingStatus]);
  
  // Handle log messages
  const handleLogMessage = useCallback((log: string) => {
    console.log(`[LiveVideoGeneration] Log: ${log}`);
    setLogs(prev => [...prev, log]);
    
    // Update status based on log message
    if (log.includes('Analyzing') || log.includes('Extracting')) {
      updateStatus(30, log, 'analyzing');
    } else if (log.includes('Rendering') || log.includes('Generating scene')) {
      updateStatus(60, log, 'generating');
    } else if (log.includes('Applying') || log.includes('Encoding') || log.includes('Optimizing')) {
      updateStatus(80, log, 'rendering');
    }
  }, [updateStatus]);
  
  // Start polling job status as fallback
  const startStatusPolling = useCallback((id: string) => {
    if (statusPollingRef.current) {
      clearInterval(statusPollingRef.current);
    }
    
    statusPollingRef.current = setInterval(async () => {
      try {
        const status = await liveApiClient.checkJobStatus(id);
        
        if (status.progress !== undefined && status.message) {
          let step: 'analyzing' | 'generating' | 'rendering' | 'complete' = 'generating';
          
          if (status.progress < 30) {
            step = 'analyzing';
          } else if (status.progress < 60) {
            step = 'generating';
          } else if (status.progress < 100) {
            step = 'rendering';
          } else {
            step = 'complete';
          }
          
          updateStatus(status.progress, status.message, step);
        }
        
        if (status.status === 'complete') {
          clearInterval(statusPollingRef.current!);
          statusPollingRef.current = null;
          
          // Get the video
          await getVideo(id);
        } else if (status.status === 'error') {
          clearInterval(statusPollingRef.current!);
          statusPollingRef.current = null;
          setError(status.message || 'An error occurred during video generation');
        }
      } catch (error) {
        console.error('[LiveVideoGeneration] Error polling status:', error);
      }
    }, 3000);
  }, [updateStatus]);
  
  // Get the generated video
  const getVideo = useCallback(async (id: string) => {
    try {
      updateStatus(95, 'Retrieving generated video...', 'rendering');
      
      let videoData: Blob | string;
      
      if (!isLiveMode) {
        // Use mock when not in live mode
        videoData = await liveApiClient.mock.getVideo();
        setVideoUrl(videoData as string);
      } else {
        // Use real API in live mode
        try {
          videoData = await liveApiClient.getVideo(id);
          const url = URL.createObjectURL(videoData as Blob);
          setVideoUrl(url);
        } catch (error) {
          console.error('[LiveVideoGeneration] Error getting video, falling back to mock:', error);
          videoData = await liveApiClient.mock.getVideo();
          setVideoUrl(videoData as string);
        }
      }
      
      updateStatus(100, 'Video generation complete!', 'complete');
      setCurrentPage('completion');
      
      // Cleanup job resources
      if (isLiveMode) {
        try {
          await liveApiClient.cleanup(id);
        } catch (error) {
          console.error('[LiveVideoGeneration] Error cleaning up job:', error);
        }
      }
      
      return videoData;
    } catch (error) {
      console.error('[LiveVideoGeneration] Error getting video:', error);
      setError(error instanceof Error ? error.message : 'Failed to retrieve video');
      updateStatus(0, 'Error retrieving video', 'complete');
      return null;
    }
  }, [setCurrentPage, updateStatus, isLiveMode]);
  
  // Handle WebSocket connection
  const connectToWebSocket = useCallback((id: string) => {
    try {
      if (!isLiveMode) {
        // Use mock when not in live mode
        console.log('[LiveVideoGeneration] Using mock log simulator');
        setIsWebSocketConnected(true);
        
        logSimulatorRef.current = liveApiClient.mock.simulateLogMessages(
          handleLogMessage,
          async () => {
            console.log('[LiveVideoGeneration] Mock generation complete');
            updateStatus(90, 'Generation complete, retrieving video...', 'rendering');
            await getVideo(id);
          }
        );
      } else {
        // Use real SSE connection in live mode
        try {
          webSocketRef.current = createLogWebSocket(
            id,
            handleLogMessage,
            (error) => {
              console.error('[LiveVideoGeneration] SSE error:', error);
              setError('Stream connection error. Falling back to polling.');
              setIsWebSocketConnected(false);
              startStatusPolling(id);
            },
            async () => {
              console.log('[LiveVideoGeneration] Generation complete via SSE');
              updateStatus(90, 'Generation complete, retrieving video...', 'rendering');
              await getVideo(id);
            }
          );
          
          setIsWebSocketConnected(true);
        } catch (error) {
          console.error('[LiveVideoGeneration] Error connecting to SSE, falling back to polling:', error);
          setIsWebSocketConnected(false);
          startStatusPolling(id);
        }
      }
    } catch (error) {
      console.error('[LiveVideoGeneration] Error in stream setup:', error);
      setIsWebSocketConnected(false);
      startStatusPolling(id);
    }
  }, [handleLogMessage, startStatusPolling, getVideo, updateStatus, isLiveMode]);
  
  // Start video generation
  const startGeneration = useCallback(async () => {
    if (!isLiveMode) {
      console.error('[LiveVideoGeneration] Cannot start live generation in demo mode');
      return;
    }
    
    try {
      setIsGenerating(true);
      setLogs([]);
      setError(null);
      setVideoUrl(null);
      cleanup();
      
      updateStatus(10, 'Connecting to generation service...', 'analyzing');
      
      let response;
      
      try {
        // Always try to use the real API in live mode
        console.log('[LiveVideoGeneration] Connecting to backend API at localhost:8000');
        response = await liveApiClient.startGeneration(inputValue);
      } catch (apiError) {
        console.error('[LiveVideoGeneration] Error connecting to backend API:', apiError);
        
        // Fallback to mock if real API fails
        console.log('[LiveVideoGeneration] Falling back to mock API');
        response = await liveApiClient.mock.startGeneration(inputValue);
      }
      
      const { job_id } = response;
      setJobId(job_id);
      
      console.log(`[LiveVideoGeneration] Generation started with job ID: ${job_id}`);
      updateStatus(20, 'Generation started, connecting to log stream...', 'analyzing');
      
      // Connect to stream for log streaming
      connectToWebSocket(job_id);
      
      return job_id;
    } catch (error) {
      console.error('[LiveVideoGeneration] Error starting generation:', error);
      setError(error instanceof Error ? error.message : 'Failed to start video generation');
      updateStatus(0, 'Error starting generation', 'analyzing');
      setIsGenerating(false);
      return null;
    }
  }, [isLiveMode, inputValue, cleanup, updateStatus, connectToWebSocket]);
  
  // Auto-start generation when in live mode and on processing page
  useEffect(() => {
    if (isLiveMode && currentPage === 'processing' && !jobId && !isGenerating) {
      console.log('[LiveVideoGeneration] Auto-starting generation in live mode');
      // Use a timeout to avoid the circular dependency issue
      const timer = setTimeout(() => {
        startGeneration().catch(err => {
          console.error('[LiveVideoGeneration] Auto-start error:', err);
          setError(err instanceof Error ? err.message : 'Failed to auto-start generation');
        });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isLiveMode, currentPage, jobId, isGenerating, startGeneration]);
  
  // Download the generated video
  const downloadVideo = useCallback(() => {
    if (!videoUrl) return;
    
    const a = document.createElement('a');
    a.href = videoUrl;
    a.download = 'generated_video.mp4';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [videoUrl]);
  
  return {
    startGeneration,
    downloadVideo,
    logs,
    error,
    isGenerating,
    videoUrl,
    jobId,
    isWebSocketConnected
  };
};
import { useState, useCallback } from 'react';
import { useAppStore } from '../store';
import { apiClient } from '../api';
import { useLiveVideoGeneration } from './useLiveVideoGeneration';

export const useVideoGeneration = () => {
  const { 
    isLiveMode, 
    setCurrentPage, 
    inputValue, 
    processingStatus, 
    setProcessingStatus 
  } = useAppStore();
  
  const [error, setError] = useState<string | null>(null);
  const [videoBlob, setVideoBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  
  // Use the live video generation hook
  const liveVideoGeneration = useLiveVideoGeneration();
  
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
  
  // Generate video in demo mode
  const generateDemoVideo = useCallback(async () => {
    try {
      setError(null);
      updateStatus(0, 'Initializing demo video...', 'generating');
      
      // Simulate progress updates for demo mode
      const steps = [
        { progress: 20, message: 'Creating scene compositions...', delay: 1000 },
        { progress: 40, message: 'Applying visual styles...', delay: 2000 },
        { progress: 60, message: 'Generating animations...', delay: 2000 },
        { progress: 80, message: 'Finalizing scene details...', delay: 2000 },
        { progress: 100, message: 'Generation complete!', delay: 1000 },
      ];
      
      for (const step of steps) {
        updateStatus(step.progress, step.message, 'generating');
        await new Promise(resolve => setTimeout(resolve, step.delay));
      }
      
      // Simulate rendering phase
      updateStatus(0, 'Starting video render...', 'rendering');
      
      const renderSteps = [
        { progress: 25, message: 'Rendering frames...', delay: 1000 },
        { progress: 50, message: 'Adding effects and transitions...', delay: 2000 },
        { progress: 75, message: 'Applying audio...', delay: 2000 },
        { progress: 100, message: 'Render complete!', delay: 1000 },
      ];
      
      for (const step of renderSteps) {
        updateStatus(step.progress, step.message, 'rendering');
        await new Promise(resolve => setTimeout(resolve, step.delay));
      }
      
      // Get demo video URL
      const demoUrl = await apiClient.mockGenerateVideo(inputValue);
      setVideoUrl(demoUrl);
      
      updateStatus(100, 'Video ready!', 'complete');
      setCurrentPage('completion');
      
      return demoUrl;
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error occurred');
      updateStatus(0, 'Error generating demo video', 'complete');
      return null;
    }
  }, [inputValue, setCurrentPage, updateStatus]);
  
  // Main function to generate video based on current mode
  const generateVideo = useCallback(async () => {
    if (isLiveMode) {
      console.log('[VideoGeneration] Using live mode generation');
      return liveVideoGeneration.startGeneration();
    } else {
      console.log('[VideoGeneration] Using demo mode generation');
      setCurrentPage('processing');
      return generateDemoVideo();
    }
  }, [isLiveMode, liveVideoGeneration, generateDemoVideo, setCurrentPage]);
  
  // Download the generated video
  const downloadVideo = useCallback(() => {
    if (isLiveMode) {
      return liveVideoGeneration.downloadVideo();
    }
    
    if (!videoUrl) return;
    
    const a = document.createElement('a');
    a.href = videoUrl;
    a.download = 'generated_video.mp4';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [isLiveMode, liveVideoGeneration, videoUrl]);
  
  return {
    generateVideo,
    downloadVideo,
    videoUrl: isLiveMode ? liveVideoGeneration.videoUrl : videoUrl,
    error: isLiveMode ? liveVideoGeneration.error : error,
    processingStatus
  };
};
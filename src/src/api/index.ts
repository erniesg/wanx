// API client for backend communication
import { useAppStore } from '../store';

// API endpoints
const API_BASE_URL = 'https://api.wanx.io';

export const API_ENDPOINTS = {
  GENERATE_VIDEO: `${API_BASE_URL}/generate_video`,
  GENERATE_SCRIPT: `${API_BASE_URL}/generate_script`,
  STREAM_LOGS: `${API_BASE_URL}/stream_logs`,
};

// Error handling wrapper
const handleApiResponse = async (response: Response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `API error: ${response.status}`);
  }
  return response;
};

// API client functions
export const apiClient = {
  // Generate video from text content
  generateVideo: async (content: string): Promise<Blob> => {
    try {
      console.log('[API] Generating video from content:', content.substring(0, 100) + '...');
      
      const response = await fetch(API_ENDPOINTS.GENERATE_VIDEO, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      });
      
      const processedResponse = await handleApiResponse(response);
      return await processedResponse.blob();
    } catch (error) {
      console.error('[API] Error generating video:', error);
      throw error;
    }
  },
  
  // Generate script from text content
  generateScript: async (content: string): Promise<any> => {
    try {
      console.log('[API] Generating script from content:', content.substring(0, 100) + '...');
      
      const response = await fetch(API_ENDPOINTS.GENERATE_SCRIPT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      });
      
      const processedResponse = await handleApiResponse(response);
      return await processedResponse.json();
    } catch (error) {
      console.error('[API] Error generating script:', error);
      throw error;
    }
  },
  
  // Mock function to simulate video generation for demo mode
  mockGenerateVideo: async (content: string): Promise<string> => {
    console.log('[API Mock] Simulating video generation for content:', content.substring(0, 100) + '...');
    
    // Return a demo video URL after a delay
    await new Promise(resolve => setTimeout(resolve, 5000));
    return "https://github.com/erniesg/wanx/raw/refs/heads/main/backend/assets/demo/output.mp4";
  }
};
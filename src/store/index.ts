import { create } from 'zustand';
import { AppState, Scene, GlobalSettings } from '../types';

const generateId = () => Math.random().toString(36).substring(2, 9);

const createDefaultScene = (): Scene => ({
  id: generateId(),
  duration: 7, // Default duration for each scene (total 21 seconds for 3 scenes)
  referenceImage: null,
  prompt: {
    subject: 'a person',
    scene: 'in a modern room',
    motion: 'moving naturally',
    camera: 'stationary',
    atmosphere: 'peaceful',
    full: ''
  },
  subtitle: '',
  voiceover: '',
  motionPreset: 'natural',
  cameraPreset: 'stationary'
});

const createDefaultGlobalSettings = (): GlobalSettings => ({
  title: 'TECH INDUSTRY UPDATE',
  coverImage: null,
  coverImageUrl: 'https://raw.githubusercontent.com/erniesg/wanx/refs/heads/main/backend/assets/demo/coverimage.png',
  atmosphere: 'energetic',
  style: 'modern'
});

// Predefined prompts for the three scenes
const scene1Prompt = "High-tech concept animation, the title \"TECH INDUSTRY UPDATE\" is suspended against the dark background of the universe, forming a sharp contrast with the bright yellow city outline. The surface of the city buildings is dotted with jumping data points, symbolizing the pulse of the information age. The camera zooms in to the left of the center, and a close-up of a high-brightness yellow chip comes into view. The exquisite circuit board details are fully revealed, and the data flow shuttles between them, like a bridge connecting the city and technology. The entire picture is filled with pixel particle effects, creating a vibrant future technology atmosphere. The city and technology elements are intertwined, showing a dynamic and integrated visual feast. The close-up to the mid-range changes to enhance the shocking sense of the technology theme.";

const scene2Prompt = "In a high-rise office, three blurry silhouettes stand in front of a large French window, with the evening city skyline and dim sky in the background. In the foreground are scattered documents and contracts, with some words such as \"technology transfer\", \"regulations\" and \"export control\" briefly highlighted. The camera switches back and forth between the documents and the figures in front of the window, and the window glass reflects data streams and news headlines. Above the documents are blurred ID photos of the three people, surrounded by technical diagrams and legal seals. The overall color tone is blue-gray, with warm orange tones, creating a mysterious and serious atmosphere.";

const scene3Prompt = "Close-up: A computer screen in 2025, with a blurred background of a nighttime city and an aerial view of a port container terminal, in warm amber tones. The screen slowly zooms out to reveal more screen details, with \"READ MORE\" and \"IN BIO\" buttons at the bottom, slightly glowing. Data visualizations flow across the screen, representing global trade routes and connections. Text and images in a browser window move slightly, suggesting news content that is updated in real time. The screen reflects the soft lighting of the keyboard and the outline of the user. The overall atmosphere is professional and mysterious, suggesting that deep content is waiting to be explored.";

// API endpoints for live mode
const API_ENDPOINTS = {
  GENERATE_SCRIPT: 'https://api.wanx.io/generate/script',
  GENERATE_VIDEO: 'https://api.wanx.io/generate/video',
  PUBLISH_TIKTOK: 'https://api.wanx.io/publish/tiktok'
};

// Default URL for demo mode
const DEFAULT_DEMO_URL = "https://www.techinasia.com/news/sg-charges-people-fraud-nvidia-chip-export-case";

export const useAppStore = create<AppState>((set, get) => ({
  globalSettings: createDefaultGlobalSettings(),
  scenes: [
    {
      ...createDefaultScene(),
      prompt: {
        subject: 'tech animation',
        scene: 'futuristic cityscape',
        motion: 'data points jumping',
        camera: 'zooming in',
        atmosphere: 'vibrant',
        full: scene1Prompt
      }
    },
    {
      ...createDefaultScene(),
      prompt: {
        subject: 'office silhouettes',
        scene: 'high-rise with city view',
        motion: 'documents highlighting',
        camera: 'switching views',
        atmosphere: 'mysterious',
        full: scene2Prompt
      }
    },
    {
      ...createDefaultScene(),
      prompt: {
        subject: 'computer screen',
        scene: 'nighttime city background',
        motion: 'data visualization flowing',
        camera: 'zooming out',
        atmosphere: 'professional',
        full: scene3Prompt
      }
    }
  ],
  totalDuration: 21, // Initial duration based on three scenes of 7 seconds each
  activeSceneId: null,
  editMode: 'interactive',
  activePromptComponent: null,
  currentPage: 'landing',
  inputType: 'url',
  inputValue: DEFAULT_DEMO_URL, // Default value for demo mode
  processingStatus: {
    step: 'analyzing',
    progress: 0,
    message: 'Initializing...'
  },
  videoUrl: 'https://github.com/erniesg/wanx/raw/refs/heads/main/backend/assets/demo/output.mp4',
  
  // Mode settings
  isLiveMode: false,

  setGlobalSettings: (settings) => {
    set((state) => ({
      globalSettings: {
        ...state.globalSettings,
        ...settings
      }
    }));
  },

  addScene: () => {
    const { scenes } = get();
    
    // Limit to 3 scenes maximum
    if (scenes.length >= 3) return;
    
    const newScene = createDefaultScene();
    set((state) => ({
      scenes: [...state.scenes, newScene],
      activeSceneId: newScene.id
    }));
    get().calculateTotalDuration();
  },

  updateScene: (id, updates) => {
    set((state) => ({
      scenes: state.scenes.map((scene) => 
        scene.id === id 
          ? { 
              ...scene, 
              ...updates,
              prompt: {
                ...scene.prompt,
                ...(updates.prompt || {}),
                full: updates.prompt?.full !== undefined ? updates.prompt.full : scene.prompt.full
              }
            } 
          : scene
      )
    }));
    get().calculateTotalDuration();
  },

  removeScene: (id) => {
    set((state) => {
      // Don't remove if it's the last scene
      if (state.scenes.length <= 1) return state;
      
      return {
        scenes: state.scenes.filter((scene) => scene.id !== id)
      };
    });
    get().calculateTotalDuration();
  },

  reorderScenes: (startIndex, endIndex) => {
    set((state) => {
      const result = Array.from(state.scenes);
      const [removed] = result.splice(startIndex, 1);
      result.splice(endIndex, 0, removed);
      return { scenes: result };
    });
  },

  setActiveScene: (id) => {
    set({ activeSceneId: id });
  },

  setEditMode: (mode) => {
    set({ editMode: mode });
  },

  setActivePromptComponent: (component) => {
    set({ activePromptComponent: component });
  },

  calculateTotalDuration: () => {
    set((state) => ({
      totalDuration: state.scenes.reduce((total, scene) => total + scene.duration, 0)
    }));
  },

  setCurrentPage: (page) => {
    set({ currentPage: page });
  },

  setInputType: (type) => {
    set({ inputType: type });
  },

  setInputValue: (value) => {
    set({ inputValue: value });
  },

  startGeneration: () => {
    const { isLiveMode } = get();
    
    set({ 
      currentPage: 'script',
      processingStatus: {
        step: 'analyzing',
        progress: 0,
        message: 'Analyzing content...'
      }
    });

    console.log(`[Mode] Starting generation in ${isLiveMode ? 'LIVE' : 'DEMO'} mode`);

    if (isLiveMode) {
      // In live mode, we would make an actual API call
      // This is a placeholder for the actual implementation
      console.log('[Live Mode] Making API call to generate script');
      
      // Simulate API call with a timeout
      setTimeout(() => {
        console.log('[Live Mode] Script generation API call completed');
        set((state) => ({
          processingStatus: {
            ...state.processingStatus,
            progress: 100,
            message: 'Analysis complete!'
          }
        }));
      }, 3000);
    } else {
      // In demo mode, we just simulate the process
      console.log('[Demo Mode] Simulating script generation');
      
      // Simulate content analysis
      setTimeout(() => {
        set((state) => ({
          processingStatus: {
            ...state.processingStatus,
            progress: 100,
            message: 'Analysis complete!'
          }
        }));
      }, 2000);
    }
  },

  generateVideo: () => {
    const { isLiveMode } = get();
    
    set({ 
      currentPage: 'processing',
      processingStatus: {
        step: 'generating',
        progress: 0,
        message: 'Generating video scenes...'
      }
    });

    console.log(`[Mode] Generating video in ${isLiveMode ? 'LIVE' : 'DEMO'} mode`);

    if (isLiveMode) {
      // In live mode, we would make an actual API call
      console.log('[Live Mode] Making API call to generate video');
      
      // Simulate the API call and processing with progress updates
      const updateLiveProgress = (progress: number, message: string, step: 'analyzing' | 'generating' | 'rendering' | 'complete') => {
        console.log(`[Live Mode] Progress update: ${progress}% - ${message}`);
        set({
          processingStatus: {
            step,
            progress,
            message
          }
        });
      };

      // Simulate API call progress
      setTimeout(() => updateLiveProgress(20, 'Sending request to AI service...', 'generating'), 1000);
      setTimeout(() => updateLiveProgress(40, 'Processing video frames...', 'generating'), 3000);
      setTimeout(() => updateLiveProgress(60, 'Applying visual effects...', 'generating'), 5000);
      setTimeout(() => updateLiveProgress(80, 'Finalizing video...', 'generating'), 7000);
      setTimeout(() => {
        updateLiveProgress(100, 'Generation complete!', 'generating');
        
        // Move to rendering step
        setTimeout(() => {
          updateLiveProgress(0, 'Starting video render...', 'rendering');
          
          setTimeout(() => updateLiveProgress(25, 'Rendering frames...', 'rendering'), 1000);
          setTimeout(() => updateLiveProgress(50, 'Adding effects and transitions...', 'rendering'), 3000);
          setTimeout(() => updateLiveProgress(75, 'Applying audio...', 'rendering'), 5000);
          setTimeout(() => {
            updateLiveProgress(100, 'Render complete!', 'rendering');
            
            // Complete the process
            setTimeout(() => {
              console.log('[Live Mode] Video generation completed');
              set({
                currentPage: 'completion',
                videoUrl: 'https://github.com/erniesg/wanx/raw/refs/heads/main/backend/assets/demo/output.mp4', // In a real app, this would be the URL returned by the API
                processingStatus: {
                  step: 'complete',
                  progress: 100,
                  message: 'Video ready!'
                }
              });
            }, 1000);
          }, 7000);
        }, 1000);
      }, 9000);
    } else {
      // In demo mode, we just simulate the process
      console.log('[Demo Mode] Simulating video generation');
      
      // Simulate the video generation process with progress updates
      const updateProgress = (progress: number, message: string, step: 'analyzing' | 'generating' | 'rendering' | 'complete') => {
        set({
          processingStatus: {
            step,
            progress,
            message
          }
        });
      };

      // Simulate generation steps
      setTimeout(() => updateProgress(20, 'Creating scene compositions...', 'generating'), 1000);
      setTimeout(() => updateProgress(40, 'Applying visual styles...', 'generating'), 3000);
      setTimeout(() => updateProgress(60, 'Generating animations...', 'generating'), 5000);
      setTimeout(() => updateProgress(80, 'Finalizing scene details...', 'generating'), 7000);
      setTimeout(() => {
        updateProgress(100, 'Generation complete!', 'generating');
        
        // Move to rendering step
        setTimeout(() => {
          updateProgress(0, 'Starting video render...', 'rendering');
          
          setTimeout(() => updateProgress(25, 'Rendering frames...', 'rendering'), 1000);
          setTimeout(() => updateProgress(50, 'Adding effects and transitions...', 'rendering'), 3000);
          setTimeout(() => updateProgress(75, 'Applying audio...', 'rendering'), 5000);
          setTimeout(() => {
            updateProgress(100, 'Render complete!', 'rendering');
            
            // Complete the process
            setTimeout(() => {
              console.log('[Demo Mode] Video generation completed');
              set({
                currentPage: 'completion',
                videoUrl: 'https://github.com/erniesg/wanx/raw/refs/heads/main/backend/assets/demo/output.mp4',
                processingStatus: {
                  step: 'complete',
                  progress: 100,
                  message: 'Video ready!'
                }
              });
            }, 1000);
          }, 7000);
        }, 1000);
      }, 9000);
    }
  },

  publishToTikTok: async () => {
    const { isLiveMode } = get();
    
    console.log(`[Mode] Publishing to TikTok in ${isLiveMode ? 'LIVE' : 'DEMO'} mode`);
    
    set((state) => ({
      processingStatus: {
        ...state.processingStatus,
        message: 'Connecting to TikTok...'
      }
    }));

    if (isLiveMode) {
      // In live mode, we would make an actual API call
      console.log('[Live Mode] Making API call to publish to TikTok');
      
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        console.log('[Live Mode] Connected to TikTok');
        set((state) => ({
          processingStatus: {
            ...state.processingStatus,
            message: 'Publishing to TikTok...'
          }
        }));
        
        // Simulate upload
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        console.log('[Live Mode] Published to TikTok successfully');
        set((state) => ({
          processingStatus: {
            ...state.processingStatus,
            message: 'Published successfully!'
          }
        }));
        
        return true;
      } catch (error) {
        console.error('[Live Mode] Error publishing to TikTok:', error);
        set((state) => ({
          processingStatus: {
            ...state.processingStatus,
            message: 'Failed to publish to TikTok'
          }
        }));
        return false;
      }
    } else {
      // In demo mode, we just simulate the process
      console.log('[Demo Mode] Simulating TikTok publication');
      
      // Simulate connection delay
      await new Promise(resolve => setTimeout(resolve, 2000));

      set((state) => ({
        processingStatus: {
          ...state.processingStatus,
          message: 'Publishing to TikTok...'
        }
      }));

      // Simulate upload delay
      await new Promise(resolve => setTimeout(resolve, 3000));

      console.log('[Demo Mode] Published to TikTok successfully');
      set((state) => ({
        processingStatus: {
          ...state.processingStatus,
          message: 'Published successfully!'
        }
      }));

      return true;
    }
  },
  
  // Mode actions
  toggleLiveMode: () => {
    set((state) => {
      const newMode = !state.isLiveMode;
      console.log(`[Mode] Switched to ${newMode ? 'LIVE' : 'DEMO'} mode`);
      
      // If switching to demo mode, set the default URL
      const inputValue = newMode ? '' : DEFAULT_DEMO_URL;
      
      return { 
        isLiveMode: newMode,
        inputValue
      };
    });
  }
}));
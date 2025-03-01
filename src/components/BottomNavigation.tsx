import React, { useState, useEffect } from 'react';
import { ArrowLeft, RefreshCw, Video } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAppStore } from '../store';
import { useVideoGeneration } from '../hooks/useVideoGeneration';

const BottomNavigation: React.FC = () => {
  const [isGenerating, setIsGenerating] = useState(false);
  const { setCurrentPage, isLiveMode } = useAppStore();
  const { generateVideo } = useVideoGeneration();

  const handleGenerateVideo = () => {
    setIsGenerating(true);
    // In a real app, this would trigger the video generation process
    setTimeout(async () => {
      await generateVideo();
      setIsGenerating(false);
    }, 1000);
  };

  const handleBack = () => {
    setCurrentPage('landing');
  };

  // Log mode changes for debugging
  useEffect(() => {
    console.log(`[BottomNavigation] Current mode: ${isLiveMode ? 'LIVE' : 'DEMO'}`);
  }, [isLiveMode]);

  return (
    <div className="cyberpunk-card p-4 flex justify-between items-center">
      <div className="scanline"></div>
      <button className="neon-button flex items-center" onClick={handleBack}>
        <ArrowLeft size={16} className="mr-2" />
        Back
      </button>
      
      <div className="flex space-x-4">
        <button className="neon-button flex items-center">
          <RefreshCw size={16} className="mr-2" />
          Regenerate
        </button>
        
        <motion.button 
          className="neon-button primary flex items-center relative overflow-visible"
          onClick={handleGenerateVideo}
          whileHover={{ scale: 1.05 }}
          disabled={isGenerating}
        >
          {/* Clapperboard animation */}
          <motion.div 
            className="absolute -left-10 top-1/2 -translate-y-1/2"
            initial={{ opacity: 0, x: 10 }}
            whileHover={{ opacity: 1, x: 0 }}
            animate={isGenerating ? { 
              opacity: 1,
              x: [0, 5, 0],
              transition: { x: { repeat: Infinity, duration: 0.5 } }
            } : {}}
          >
            <motion.div 
              className="w-8 h-7 bg-black border border-white relative overflow-hidden"
              initial={{ rotateX: 0 }}
              whileHover={{ rotateX: [0, 70, 0], transition: { duration: 0.5 } }}
              animate={isGenerating ? { 
                rotateX: [0, 70, 0],
                transition: { repeat: Infinity, duration: 0.5 }
              } : {}}
            >
              {/* Clapperboard stripes */}
              {[...Array(3)].map((_, i) => (
                <div 
                  key={i} 
                  className="absolute h-1 bg-white left-0 right-0" 
                  style={{ top: `${(i + 1) * 20}%` }}
                />
              ))}
              
              {/* Clapperboard top part */}
              <motion.div 
                className="absolute top-0 left-0 right-0 h-2/5 bg-black border-b border-white"
                initial={{ rotateX: 0 }}
                animate={isGenerating ? { 
                  rotateX: [0, 70, 0],
                  transition: { repeat: Infinity, duration: 0.5 }
                } : {}}
                style={{ transformOrigin: "top" }}
              >
                {[...Array(3)].map((_, i) => (
                  <div 
                    key={i} 
                    className="absolute h-1 bg-white left-0 right-0" 
                    style={{ top: `${(i + 1) * 30}%` }}
                  />
                ))}
              </motion.div>
            </motion.div>
          </motion.div>
          
          <Video size={16} className="mr-2" />
          {isGenerating ? "Generating..." : "Generate Video"}
        </motion.button>
      </div>
      
      {isLiveMode && (
        <div className="absolute -top-4 right-4 bg-green-900 text-green-300 text-xs px-2 py-1 rounded-full flex items-center">
          <div className="live-indicator mr-1"></div>
          Live Mode
        </div>
      )}
    </div>
  );
};

export default BottomNavigation;
import React, { useEffect, useState, useRef } from 'react';
import { useAppStore } from '../store';
import { motion } from 'framer-motion';
import PageHeader from './PageHeader';
import Footer from './Footer';

const ProcessingPage: React.FC = () => {
  const { processingStatus, isLiveMode } = useAppStore();
  const { step, progress, message } = processingStatus;
  const [logs, setLogs] = useState<string[]>([]);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Simulated log messages
  useEffect(() => {
    const demoLogMessages = [
      "Initializing video generation process...",
      "Analyzing content structure...",
      "Extracting key themes and topics...",
      "Generating scene compositions...",
      "Creating visual elements for scene 1...",
      "Applying style parameters to visuals...",
      "Optimizing for TikTok vertical format...",
      "Generating transitions between scenes...",
      "Rendering frame 1 of 720...",
      "Rendering frame 120 of 720...",
      "Rendering frame 240 of 720...",
      "Rendering frame 360 of 720...",
      "Rendering frame 480 of 720...",
      "Rendering frame 600 of 720...",
      "Finalizing video render...",
      "Applying audio synchronization...",
      "Optimizing video compression...",
      "Preparing final output..."
    ];

    const liveLogMessages = [
      "Connecting to AI video generation service...",
      "Authenticating connection...",
      "Sending script data to API...",
      "API received request, processing...",
      "Initializing AI model for video generation...",
      "Loading scene generation parameters...",
      "AI generating visual concepts for scene 1...",
      "Applying style transfer to generated frames...",
      "Processing scene transitions...",
      "Rendering video frames with GPU acceleration...",
      "Applying motion effects to scene elements...",
      "Generating audio track from script...",
      "Synchronizing audio with visual elements...",
      "Optimizing video for TikTok platform...",
      "Applying final compression and encoding...",
      "Preparing to deliver completed video..."
    ];

    const logMessages = isLiveMode ? liveLogMessages : demoLogMessages;
    console.log(`[ProcessingPage] Using ${isLiveMode ? 'LIVE' : 'DEMO'} mode logs`);

    const addLogMessage = (index: number) => {
      if (index < logMessages.length) {
        setLogs(prev => [...prev, logMessages[index]]);
        setTimeout(() => addLogMessage(index + 1), Math.random() * 2000 + 1000);
      }
    };

    // Clear logs when mode changes
    setLogs([]);
    addLogMessage(0);
  }, [isLiveMode]);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-background-dark to-background-darker flex flex-col">
      <div className="cyber-grid"></div>
      
      <div className="container mx-auto px-4 py-16 flex-grow flex flex-col items-center justify-center">
        <PageHeader 
          title="Creating Your Video"
          subtitle={null}
        />
        
        <motion.div 
          className="w-full max-w-3xl"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="cyberpunk-card p-6 md:p-8 mb-8">
            <div className="scanline"></div>
            
            {/* Progress bar */}
            <div className="progress-container mb-2">
              <div 
                className="progress-bar"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
            
            <div className="flex justify-between items-center mb-6">
              <span className="text-sm text-gray-400">{message}</span>
              <span className="text-sm font-medium">{progress}%</span>
            </div>
            
            {/* Clapperboard animation */}
            <div className="flex justify-center mb-6">
              <motion.div 
                className="w-16 h-14 bg-black border border-white relative overflow-hidden"
                animate={{ 
                  rotateY: [0, 10, 0],
                  transition: { repeat: Infinity, duration: 2 }
                }}
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
                  animate={{ 
                    rotateX: [0, 70, 0],
                    transition: { repeat: Infinity, duration: 2 }
                  }}
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
            </div>
          </div>
          
          <div className="cyberpunk-card p-6">
            <div className="scanline"></div>
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-orbitron text-secondary-cyan">Log</h2>
              <div className="flex items-center">
                <span className={`text-xs px-2 py-1 rounded-full ${isLiveMode ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-300'}`}>
                  {isLiveMode ? 'Live Mode' : 'Demo Mode'}
                </span>
              </div>
            </div>
            
            <div 
              ref={logContainerRef}
              className="bg-background-dark p-4 rounded-sm h-60 overflow-y-auto font-mono text-sm"
            >
              {logs.map((log, index) => (
                <div key={index} className="mb-1 text-gray-300">
                  <span className="text-secondary-cyan mr-2">[{new Date().toLocaleTimeString()}]</span>
                  {log}
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
      
      <Footer />
    </div>
  );
};

export default ProcessingPage;
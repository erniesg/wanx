import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store';
import { motion } from 'framer-motion';
import { Download, Home } from 'lucide-react';
import PageHeader from './PageHeader';
import Footer from './Footer';

const CompletionPage: React.FC = () => {
  const { videoUrl, processingStatus, publishToTikTok, setCurrentPage, isLiveMode } = useAppStore();
  const [isPublishing, setIsPublishing] = useState(false);
  const [isPublished, setIsPublished] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);

  // Log mode for debugging
  useEffect(() => {
    console.log(`[CompletionPage] Current mode: ${isLiveMode ? 'LIVE' : 'DEMO'}`);
  }, [isLiveMode]);

  const handlePublishToTikTok = async () => {
    setShowConnectModal(true);
  };

  const handleConnectAccount = async () => {
    setShowConnectModal(false);
    setIsPublishing(true);
    
    try {
      const success = await publishToTikTok();
      if (success) {
        setIsPublished(true);
      }
    } catch (error) {
      console.error('Failed to publish:', error);
    } finally {
      setIsPublishing(false);
    }
  };

  const handleDownload = () => {
    // Create an anchor element and trigger download
    const downloadLink = document.createElement('a');
    downloadLink.href = "https://github.com/erniesg/wanx/raw/refs/heads/main/backend/assets/demo/output.mp4";
    downloadLink.download = "tech_industry_update.mp4";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  };

  const handleGoHome = () => {
    setCurrentPage('landing');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background-dark to-background-darker flex flex-col">
      <div className="cyber-grid"></div>
      
      <div className="container mx-auto px-4 py-8 flex-grow">
        <PageHeader 
          subtitle={null}
        />
        
        <motion.div 
          className="w-full max-w-4xl mx-auto"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-3xl md:text-4xl font-orbitron text-secondary-cyan">
              {isPublished ? (
                <>
                  You're <span className="line-through">Almost</span>{' '}
                  <span className="famous-text">Famous!</span>
                </>
              ) : (
                <>
                  You're Almost Famous!
                </>
              )}
            </h1>
            <div className="flex items-center space-x-3">
              <div className={`text-xs px-2 py-1 rounded-full ${isLiveMode ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-300'}`}>
                {isLiveMode ? 'Live Mode' : 'Demo Mode'}
              </div>
              <button 
                onClick={handleGoHome}
                className="neon-button flex items-center"
              >
                <Home size={16} className="mr-2" />
                Home
              </button>
            </div>
          </div>
          
          <div className="cyberpunk-card p-6 mb-8">
            <div className="scanline"></div>
            
            <div className="flex flex-col md:flex-row items-center gap-6">
              <div className="video-player md:w-1/3 w-full aspect-[9/16] mx-auto">
                <video 
                  src="https://github.com/erniesg/wanx/raw/refs/heads/main/backend/assets/demo/output.mp4" 
                  controls 
                  className="w-full h-full object-cover"
                  autoPlay
                  loop
                ></video>
              </div>
              
              <div className="md:w-2/3 w-full flex flex-col justify-center space-y-6">
                <div className="text-center md:text-left">
                  <h2 className="text-xl font-orbitron mb-2 text-secondary-cyan">TikTok Ready</h2>
                  <p className="text-gray-300">
                    {isPublished 
                      ? "Your video is now live on TikTok! The magic has begun."
                      : "Hit publish and watch magic happen."}
                  </p>
                </div>
                
                <div className="flex flex-col space-y-4">
                  <button 
                    className="neon-button flex items-center justify-center"
                    onClick={handleDownload}
                  >
                    <Download size={16} className="mr-2" />
                    Download Video
                  </button>
                  
                  <motion.button 
                    className="neon-button primary flex items-center justify-center relative overflow-visible"
                    onClick={handlePublishToTikTok}
                    whileHover={{ scale: 1.05 }}
                    disabled={isPublishing || isPublished}
                    animate={{
                      boxShadow: isPublished 
                        ? '0 0 20px rgba(0, 255, 255, 0.8)'
                        : ['0 0 0 rgba(0, 255, 255, 0)', '0 0 20px rgba(0, 255, 255, 0.8)', '0 0 0 rgba(0, 255, 255, 0)'],
                    }}
                    transition={{
                      boxShadow: {
                        repeat: isPublished ? 0 : Infinity,
                        duration: 2
                      }
                    }}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 448 512" fill="currentColor" className="mr-2">
                      <path d="M448,209.91a210.06,210.06,0,0,1-122.77-39.25V349.38A162.55,162.55,0,1,1,185,188.31V278.2a74.62,74.62,0,1,0,52.23,71.18V0l88,0a121.18,121.18,0,0,0,1.86,22.17h0A122.18,122.18,0,0,0,381,102.39a121.43,121.43,0,0,0,67,20.14Z" />
                    </svg>
                    {isPublished ? 'Published to TikTok' : isPublishing ? 'Publishing...' : 'Publish to TikTok'}
                  </motion.button>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
      
      <Footer />
      
      {/* TikTok Connect Modal */}
      {showConnectModal && (
        <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
          <div className="cyberpunk-card w-full max-w-md p-6">
            <div className="scanline"></div>
            <h2 className="text-xl font-orbitron mb-4 text-secondary-cyan">Connect to TikTok</h2>
            
            <p className="mb-6 text-gray-300">
              To publish your video directly to TikTok, you need to connect your TikTok account.
              {isLiveMode && (
                <span className="block mt-2 text-green-300">
                  Live Mode: This will attempt to connect to the actual TikTok API.
                </span>
              )}
            </p>
            
            <div className="flex space-x-4">
              <button 
                className="neon-button flex-1"
                onClick={() => setShowConnectModal(false)}
              >
                Cancel
              </button>
              <button 
                className="social-button tiktok flex-1 h-10"
                onClick={handleConnectAccount}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 448 512" fill="currentColor" className="mr-2">
                  <path d="M448,209.91a210.06,210.06,0,0,1-122.77-39.25V349.38A162.55,162.55,0,1,1,185,188.31V278.2a74.62,74.62,0,1,0,52.23,71.18V0l88,0a121.18,121.18,0,0,0,1.86,22.17h0A122.18,122.18,0,0,0,381,102.39a121.43,121.43,0,0,0,67,20.14Z" />
                </svg>
                Connect TikTok
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CompletionPage;
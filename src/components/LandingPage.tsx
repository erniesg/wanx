import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store';
import { motion } from 'framer-motion';
import { Link, FileText, ArrowRight, Sparkles, Zap, Sliders } from 'lucide-react';
import PageHeader from './PageHeader';
import Footer from './Footer';

const LandingPage: React.FC = () => {
  const { inputType, setInputType, inputValue, setInputValue, startGeneration } = useAppStore();
  const [isInputValid, setIsInputValid] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationMessage, setGenerationMessage] = useState('');
  const [logs, setLogs] = useState<string[]>([]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInputValue(value);
    setIsInputValid(value.trim().length > 0);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isInputValid) {
      setIsGenerating(true);
      simulateGeneration();
    }
  };

  const simulateGeneration = () => {
    // Reset logs and progress
    setLogs([]);
    setGenerationProgress(0);
    setGenerationMessage('Initializing content analysis...');
    
    // Simulated log messages for content analysis
    const analysisLogs = [
      "Connecting to content source...",
      "Extracting main content...",
      "Analyzing text structure...",
      "Identifying key topics and themes...",
      "Determining content sentiment...",
      "Extracting relevant keywords...",
      "Generating content summary...",
      "Creating scene outlines...",
      "Optimizing for TikTok format...",
      "Finalizing script generation..."
    ];

    // Add log messages with delays
    let currentLog = 0;
    const addLogMessage = () => {
      if (currentLog < analysisLogs.length) {
        setLogs(prev => [...prev, analysisLogs[currentLog]]);
        currentLog++;
        setTimeout(addLogMessage, Math.random() * 1000 + 500);
      }
    };

    // Start adding logs
    addLogMessage();

    // Simulate progress updates
    const progressSteps = [
      { progress: 10, message: 'Analyzing content structure...', delay: 1000 },
      { progress: 25, message: 'Extracting key themes...', delay: 2000 },
      { progress: 40, message: 'Generating scene compositions...', delay: 2000 },
      { progress: 60, message: 'Creating visual concepts...', delay: 1500 },
      { progress: 75, message: 'Optimizing for TikTok format...', delay: 1500 },
      { progress: 90, message: 'Finalizing script...', delay: 1000 },
      { progress: 100, message: 'Script generation complete!', delay: 1000 }
    ];

    let currentStep = 0;
    const updateProgress = () => {
      if (currentStep < progressSteps.length) {
        const step = progressSteps[currentStep];
        setGenerationProgress(step.progress);
        setGenerationMessage(step.message);
        currentStep++;
        
        if (currentStep < progressSteps.length) {
          setTimeout(updateProgress, step.delay);
        } else {
          // Final step - complete the generation
          setTimeout(() => {
            startGeneration();
            setIsGenerating(false);
          }, step.delay);
        }
      }
    };

    // Start progress updates
    setTimeout(updateProgress, 1000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background-dark to-background-darker flex flex-col">
      <div className="cyber-grid"></div>
      
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16 flex-grow flex flex-col items-center justify-center relative">
        <PageHeader subtitle="Text to TikTok in 3 easy steps: Type, Review, Publish!" />
        
        {!isGenerating ? (
          <motion.div 
            className="w-full max-w-2xl cyberpunk-card p-6 md:p-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.6 }}
          >
            <div className="scanline"></div>
            <div className="flex mb-6">
              <button 
                className={`flex-1 py-2 flex justify-center items-center ${inputType === 'url' ? 'text-secondary-cyan border-b-2 border-secondary-cyan' : 'text-gray-400'}`}
                onClick={() => setInputType('url')}
              >
                <Link size={18} className="mr-2" />
                URL
              </button>
              <button 
                className={`flex-1 py-2 flex justify-center items-center ${inputType === 'text' ? 'text-secondary-cyan border-b-2 border-secondary-cyan' : 'text-gray-400'}`}
                onClick={() => setInputType('text')}
              >
                <FileText size={18} className="mr-2" />
                Text
              </button>
            </div>
            
            <form onSubmit={handleSubmit}>
              {inputType === 'url' ? (
                <div className="mb-6">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={handleInputChange}
                    placeholder="Paste URL here..."
                    className="input-field py-3 bg-background-dark"
                  />
                </div>
              ) : (
                <div className="mb-6">
                  <textarea
                    value={inputValue}
                    onChange={handleInputChange}
                    placeholder="Paste your text here..."
                    className="input-field min-h-32 py-3 bg-background-dark"
                  ></textarea>
                </div>
              )}
              
              <button 
                type="submit"
                className="neon-button primary w-full py-3 flex items-center justify-center"
                disabled={!isInputValid}
              >
                <Sparkles size={18} className="mr-2" />
                Start Generating
                <ArrowRight size={18} className="ml-2" />
              </button>
            </form>
          </motion.div>
        ) : (
          <motion.div 
            className="w-full max-w-3xl"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-3xl md:text-4xl font-orbitron text-center mb-8 text-secondary-cyan">
              Analyzing Your Content
            </h1>
            
            <div className="cyberpunk-card p-6 md:p-8 mb-8">
              <div className="scanline"></div>
              
              {/* Progress bar */}
              <div className="progress-container mb-2">
                <div 
                  className="progress-bar"
                  style={{ width: `${generationProgress}%` }}
                ></div>
              </div>
              
              <div className="flex justify-between items-center mb-6">
                <span className="text-sm text-gray-400">{generationMessage}</span>
                <span className="text-sm font-medium">{generationProgress}%</span>
              </div>
              
              {/* AI analysis animation */}
              <div className="flex justify-center mb-6">
                <motion.div 
                  className="w-16 h-16 relative"
                  animate={{ 
                    rotate: 360,
                    transition: { repeat: Infinity, duration: 8, ease: "linear" }
                  }}
                >
                  <div className="absolute inset-0 border-2 border-secondary-cyan rounded-full opacity-20"></div>
                  <motion.div 
                    className="absolute w-4 h-4 bg-secondary-cyan rounded-full"
                    style={{ top: 0, left: '50%', marginLeft: '-8px' }}
                    animate={{ 
                      scale: [1, 1.5, 1],
                      transition: { repeat: Infinity, duration: 2 }
                    }}
                  ></motion.div>
                  <motion.div 
                    className="absolute w-3 h-3 bg-primary-magenta rounded-full"
                    style={{ bottom: '25%', right: 0 }}
                    animate={{ 
                      scale: [1, 1.3, 1],
                      transition: { repeat: Infinity, duration: 1.5, delay: 0.5 }
                    }}
                  ></motion.div>
                  <motion.div 
                    className="absolute w-2 h-2 bg-white rounded-full"
                    style={{ bottom: 0, left: '25%' }}
                    animate={{ 
                      scale: [1, 1.8, 1],
                      transition: { repeat: Infinity, duration: 1.8, delay: 1 }
                    }}
                  ></motion.div>
                </motion.div>
              </div>
            </div>
            
            <div className="cyberpunk-card p-6">
              <div className="scanline"></div>
              <h2 className="text-xl font-orbitron mb-4 text-secondary-cyan">Analysis Log</h2>
              
              <div 
                className="bg-background-dark p-4 rounded-sm h-60 overflow-y-auto font-mono text-sm"
              >
                {logs.map((log, index) => (
                  <div key={index} className="mb-1 text-gray-300">
                    <span className="text-secondary-cyan mr-2">[{new Date().toLocaleTimeString()}]</span>
                    {log}
                  </div>
                ))}
                {logs.length === 0 && (
                  <div className="text-gray-500 italic">Initializing analysis...</div>
                )}
              </div>
            </div>
          </motion.div>
        )}
        
        <motion.div 
          className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.6 }}
        >
          <div className="cyberpunk-card p-4 text-center">
            <div className="scanline"></div>
            <div className="w-12 h-12 rounded-full bg-gradient-primary flex items-center justify-center mx-auto mb-3">
              <Zap size={24} />
            </div>
            <h3 className="text-lg font-orbitron mb-2 text-secondary-cyan">Effortless</h3>
            <p className="text-sm text-gray-300">Create videos in just a few clicks—simple, fast, and automatic.</p>
          </div>
          
          <div className="cyberpunk-card p-4 text-center">
            <div className="scanline"></div>
            <div className="w-12 h-12 rounded-full bg-gradient-primary flex items-center justify-center mx-auto mb-3">
              <Sparkles size={24} />
            </div>
            <h3 className="text-lg font-orbitron mb-2 text-secondary-cyan">AI-Powered</h3>
            <p className="text-sm text-gray-300">Truly multimodal: image, video, audio, and voiceover generated seamlessly.</p>
          </div>
          
          <div className="cyberpunk-card p-4 text-center">
            <div className="scanline"></div>
            <div className="w-12 h-12 rounded-full bg-gradient-primary flex items-center justify-center mx-auto mb-3">
              <Sliders size={24} />
            </div>
            <h3 className="text-lg font-orbitron mb-2 text-secondary-cyan">Control</h3>
            <p className="text-sm text-gray-300">Craft the perfect prompt to shape your video as envisioned.</p>
          </div>
        </motion.div>
      </div>
      
      <Footer />
    </div>
  );
};

export default LandingPage;
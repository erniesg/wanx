import React from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '../store';
import { Zap } from 'lucide-react';

const ModeToggle: React.FC = () => {
  const { isLiveMode, toggleLiveMode } = useAppStore();

  return (
    <div className="fixed top-4 right-4 z-50">
      <button
        onClick={toggleLiveMode}
        className="flex items-center space-x-2 bg-background-dark border border-gray-700 rounded-full px-3 py-1 hover:border-secondary-cyan transition-colors"
        title={isLiveMode ? "Switch to Demo Mode" : "Switch to Live Mode"}
      >
        <span className="text-xs font-medium">
          {isLiveMode ? 'Live!' : 'Demo'}
        </span>
        
        {isLiveMode ? (
          <motion.div 
            className="relative"
            initial={{ scale: 0.8 }}
            animate={{ scale: [0.8, 1.2, 0.8] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
          >
            <div className="live-indicator"></div>
            <motion.div 
              className="absolute inset-0 bg-green-500 rounded-full"
              initial={{ opacity: 0.7, scale: 1 }}
              animate={{ opacity: 0, scale: 2 }}
              transition={{ repeat: Infinity, duration: 1.5 }}
            ></motion.div>
          </motion.div>
        ) : (
          <Zap size={14} className="text-gray-400" />
        )}
      </button>
    </div>
  );
};

export default ModeToggle;
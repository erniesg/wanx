import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import { COMPONENT_GUIDES } from '../../types';

interface PromptComponentPopupProps {
  component: string;
  value: string;
  onSave: (value: string) => void;
  onClose: () => void;
}

const PromptComponentPopup: React.FC<PromptComponentPopupProps> = ({
  component,
  value,
  onSave,
  onClose
}) => {
  const [inputValue, setInputValue] = useState(value);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  
  // If no guide is found, use a default guide to prevent null rendering
  const defaultGuide = {
    title: component.charAt(0).toUpperCase() + component.slice(1),
    tooltip: `Information about ${component}`,
    description: `This is the ${component} component of your prompt.`,
    recommendations: ["Be specific", "Use descriptive language"],
    examples: [`Example ${component}`]
  };

  const guide = COMPONENT_GUIDES[component] || defaultGuide;
  
  useEffect(() => {
    // Focus the input when the popup appears
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.setSelectionRange(0, inputRef.current.value.length);
    }
  }, []);

  // Close popup when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onClose]);

  const handleSave = () => {
    onSave(inputValue);
    onClose();
  };

  const getComponentColor = () => {
    switch (component) {
      case 'subject': return 'text-prompt-subject border-prompt-subject';
      case 'scene': return 'text-prompt-scene border-prompt-scene';
      case 'motion': return 'text-prompt-motion border-prompt-motion';
      case 'camera': return 'text-prompt-camera border-prompt-camera';
      case 'atmosphere': return 'text-prompt-atmosphere border-prompt-atmosphere';
      default: return 'text-white border-white';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <motion.div
        className="cyberpunk-card w-full max-w-md p-6 m-4"
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        ref={popupRef}
      >
        <div className="scanline"></div>
        <div className="flex justify-between items-center mb-4">
          <h3 className={`text-xl font-orbitron ${getComponentColor()}`}>
            Edit {guide?.title || component}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>
        
        {guide && (
          <div className="mb-4">
            <p className="text-sm text-gray-300 mb-2">{guide.description}</p>
            
            <div className="bg-background-dark p-3 rounded-sm mb-3">
              <h4 className="text-sm font-bold mb-1">Recommendations:</h4>
              <ul className="text-xs space-y-1 list-disc pl-4">
                {guide.recommendations.map((rec, index) => (
                  <li key={index}>{rec}</li>
                ))}
              </ul>
            </div>
            
            <div className="bg-background-dark p-3 rounded-sm">
              <h4 className="text-sm font-bold mb-1">Examples:</h4>
              <ul className="text-xs space-y-1">
                {guide.examples.map((example, index) => (
                  <li key={index} className={`${getComponentColor()} cursor-pointer hover:opacity-80`} onClick={() => setInputValue(example)}>
                    "{example}"
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        
        <textarea
          ref={inputRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className={`w-full h-32 p-3 bg-background-dark border rounded-sm focus:outline-none ${getComponentColor()}`}
        />
        
        <div className="flex justify-end mt-4 space-x-3">
          <button
            onClick={onClose}
            className="neon-button"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="neon-button primary"
          >
            Apply
          </button>
        </div>
      </motion.div>
    </div>
  );
};

export default PromptComponentPopup;
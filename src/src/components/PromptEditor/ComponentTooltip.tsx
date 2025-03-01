import React, { useState, useRef, useEffect } from 'react';
import { HelpCircle, X } from 'lucide-react';
import { COMPONENT_GUIDES } from '../../types';

interface ComponentTooltipProps {
  component: string;
}

const ComponentTooltip: React.FC<ComponentTooltipProps> = ({ component }) => {
  const [isOpen, setIsOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  
  // If no guide is found, use a default guide to prevent null rendering
  const defaultGuide = {
    title: component.charAt(0).toUpperCase() + component.slice(1),
    tooltip: `Information about ${component}`,
    description: `This is the ${component} component of your prompt.`,
    recommendations: ["Be specific", "Use descriptive language"],
    examples: [`Example ${component}`]
  };

  const guide = COMPONENT_GUIDES[component] || defaultGuide;

  // Update tooltip position when it opens and on scroll/resize
  const updateTooltipPosition = () => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const tooltipWidth = 320; // Approximate width of tooltip
      const tooltipHeight = tooltipRef.current?.offsetHeight || 300; // Fallback height
      
      // Calculate horizontal position (centered on button if possible)
      const leftPosition = Math.min(
        Math.max(10, rect.left - tooltipWidth / 2 + rect.width / 2),
        viewportWidth - tooltipWidth - 10
      );
      
      // Calculate vertical position (below button, but flip above if not enough space)
      let topPosition = rect.bottom + 5;
      
      // If tooltip would go off bottom of screen, position it above the button instead
      if (topPosition + tooltipHeight > viewportHeight) {
        topPosition = Math.max(10, rect.top - tooltipHeight - 5);
      }
      
      setTooltipPosition({
        top: topPosition,
        left: leftPosition
      });
    }
  };

  const handleButtonClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsOpen(!isOpen);
  };

  useEffect(() => {
    if (isOpen) {
      // Initial position calculation
      updateTooltipPosition();
      
      // Add event listeners for scroll and resize
      window.addEventListener('scroll', updateTooltipPosition, true);
      window.addEventListener('resize', updateTooltipPosition);
      
      return () => {
        window.removeEventListener('scroll', updateTooltipPosition, true);
        window.removeEventListener('resize', updateTooltipPosition);
      };
    }
  }, [isOpen]);

  // Close tooltip when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isOpen && 
        buttonRef.current && 
        !buttonRef.current.contains(event.target as Node) &&
        tooltipRef.current && 
        !tooltipRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const getComponentColor = () => {
    switch (component) {
      case 'subject': return 'text-prompt-subject border-prompt-subject';
      case 'scene': return 'text-prompt-scene border-prompt-scene';
      case 'motion': return 'text-prompt-motion border-prompt-motion';
      case 'camera': return 'text-prompt-camera border-prompt-camera';
      case 'atmosphere': return 'text-prompt-atmosphere border-prompt-atmosphere';
      case 'style': return 'text-secondary-cyan border-secondary-cyan';
      case 'full': return 'text-secondary-cyan border-secondary-cyan';
      default: return 'text-white border-white';
    }
  };

  return (
    <div className="relative inline-block ml-2">
      <button
        type="button"
        onClick={handleButtonClick}
        className={`text-gray-400 hover:${getComponentColor().split(' ')[0]} transition-colors`}
        ref={buttonRef}
        aria-label={`Help for ${guide.title}`}
      >
        <HelpCircle size={16} />
      </button>

      {isOpen && (
        <>
          <div 
            className="fixed inset-0 z-[9990]" 
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div
            className="fixed z-[9999] bg-ui-card shadow-lg rounded-sm border border-gray-700 p-4 w-80 max-h-[80vh] overflow-y-auto"
            style={{
              top: `${tooltipPosition.top}px`,
              left: `${tooltipPosition.left}px`,
            }}
            ref={tooltipRef}
          >
            <div className="flex justify-between items-center mb-2">
              <h3 className={`text-lg font-orbitron ${getComponentColor()}`}>{guide.title}</h3>
              <button 
                onClick={() => setIsOpen(false)} 
                className="text-gray-400 hover:text-white"
                aria-label="Close tooltip"
              >
                <X size={16} />
              </button>
            </div>
            
            <p className="text-sm mb-3">{guide.description}</p>
            
            <div className="mb-3">
              <h4 className="text-sm font-bold mb-1">Recommendations:</h4>
              <ul className="text-xs space-y-1 list-disc pl-4">
                {guide.recommendations.map((rec, index) => (
                  <li key={index}>{rec}</li>
                ))}
              </ul>
            </div>
            
            <div>
              <h4 className="text-sm font-bold mb-1">Examples:</h4>
              <ul className="text-xs space-y-1 list-disc pl-4">
                {guide.examples.map((example, index) => (
                  <li key={index} className={getComponentColor()}>{example}</li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ComponentTooltip;
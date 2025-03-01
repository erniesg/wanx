import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import ComponentTooltip from './ComponentTooltip';

interface PromptTextProps {
  prompt: {
    subject: string;
    scene: string;
    motion: string;
    camera: string;
    atmosphere: string;
    full: string;
  };
  onComponentClick: (component: string) => void;
  highlightComponent: string | null;
  onFullPromptChange: (value: string) => void;
  bgColor?: string;
  onComponentHover: (component: string | null) => void;
}

const PromptText: React.FC<PromptTextProps> = ({
  prompt,
  onComponentClick,
  highlightComponent,
  onFullPromptChange,
  bgColor = "background-dark",
  onComponentHover
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleTextClick = () => {
    setIsEditing(true);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(0, textareaRef.current.value.length);
      }
    }, 0);
  };

  const handleBlur = () => {
    setIsEditing(false);
  };

  const renderPromptComponents = () => {
    return (
      <>
        <span 
          className={`subject cursor-pointer ${highlightComponent === 'subject' ? 'relative' : ''}`}
          onClick={() => onComponentClick('subject')}
          onMouseEnter={() => onComponentHover('subject')}
          onMouseLeave={() => onComponentHover(null)}
        >
          {prompt.subject}
          {highlightComponent === 'subject' && (
            <motion.span 
              className="absolute bottom-0 left-0 right-0 h-0.5 bg-prompt-subject" 
              layoutId="highlight"
            />
          )}
        </span>
        {' '}
        <span 
          className={`scene cursor-pointer ${highlightComponent === 'scene' ? 'relative' : ''}`}
          onClick={() => onComponentClick('scene')}
          onMouseEnter={() => onComponentHover('scene')}
          onMouseLeave={() => onComponentHover(null)}
        >
          {prompt.scene}
          {highlightComponent === 'scene' && (
            <motion.span 
              className="absolute bottom-0 left-0 right-0 h-0.5 bg-prompt-scene" 
              layoutId="highlight"
            />
          )}
        </span>
        {', '}
        <span 
          className={`motion cursor-pointer ${highlightComponent === 'motion' ? 'relative' : ''}`}
          onClick={() => onComponentClick('motion')}
          onMouseEnter={() => onComponentHover('motion')}
          onMouseLeave={() => onComponentHover(null)}
        >
          {prompt.motion}
          {highlightComponent === 'motion' && (
            <motion.span 
              className="absolute bottom-0 left-0 right-0 h-0.5 bg-prompt-motion" 
              layoutId="highlight"
            />
          )}
        </span>
        {', '}
        <span 
          className={`camera cursor-pointer ${highlightComponent === 'camera' ? 'relative' : ''}`}
          onClick={() => onComponentClick('camera')}
          onMouseEnter={() => onComponentHover('camera')}
          onMouseLeave={() => onComponentHover(null)}
        >
          {prompt.camera}
          {highlightComponent === 'camera' && (
            <motion.span 
              className="absolute bottom-0 left-0 right-0 h-0.5 bg-prompt-camera" 
              layoutId="highlight"
            />
          )}
        </span>
        {', '}
        <span 
          className={`atmosphere cursor-pointer ${highlightComponent === 'atmosphere' ? 'relative' : ''}`}
          onClick={() => onComponentClick('atmosphere')}
          onMouseEnter={() => onComponentHover('atmosphere')}
          onMouseLeave={() => onComponentHover(null)}
        >
          {prompt.atmosphere}
          {highlightComponent === 'atmosphere' && (
            <motion.span 
              className="absolute bottom-0 left-0 right-0 h-0.5 bg-prompt-atmosphere" 
              layoutId="highlight"
            />
          )}
          {' atmosphere'}
        </span>
      </>
    );
  };

  return (
    <div 
      className={`prompt-text p-4 rounded-sm relative border ${isEditing 
        ? `bg-${bgColor} border-secondary-cyan` 
        : `bg-${bgColor} border-gray-700 hover:border-secondary-cyan cursor-pointer`}`}
      onClick={!isEditing ? handleTextClick : undefined}
    >
      {isEditing ? (
        <textarea
          ref={textareaRef}
          value={prompt.full || `${prompt.subject} ${prompt.scene}, ${prompt.motion}, ${prompt.camera}, ${prompt.atmosphere} atmosphere`}
          onChange={(e) => onFullPromptChange(e.target.value)}
          onBlur={handleBlur}
          className="w-full h-24 bg-transparent outline-none resize-none text-white"
        />
      ) : (
        prompt.full ? prompt.full : renderPromptComponents()
      )}
      
      {!isEditing && (
        <div className="absolute top-1 right-1 flex items-center">
          <span className="text-xs text-gray-400 mr-1">Click to edit full prompt</span>
          <ComponentTooltip component="full" />
        </div>
      )}
    </div>
  );
};

export default PromptText;
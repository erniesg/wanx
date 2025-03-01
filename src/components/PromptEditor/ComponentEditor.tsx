import React from 'react';
import { Scene } from '../../types';
import { COMPONENT_GUIDES } from '../../types';
import { HelpCircle } from 'lucide-react';
import ComponentTooltip from './ComponentTooltip';

interface ComponentEditorProps {
  scene: Scene;
  onUpdate: (updates: Partial<Scene>) => void;
  bgColor?: string;
}

const ComponentEditor: React.FC<ComponentEditorProps> = ({ scene, onUpdate, bgColor = "background-dark" }) => {
  const handlePromptChange = (component: string, value: string) => {
    onUpdate({
      prompt: {
        ...scene.prompt,
        [component]: value
      }
    });
  };

  return (
    <div className="component-editor grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <div className="flex items-center mb-1">
          <label className="text-sm font-medium text-prompt-subject">Subject</label>
          <ComponentTooltip component="subject" />
        </div>
        <input
          type="text"
          value={scene.prompt.subject}
          onChange={(e) => handlePromptChange('subject', e.target.value)}
          className="input-field border-prompt-subject bg-background-dark"
          placeholder="What is the main subject?"
        />
      </div>
      
      <div>
        <div className="flex items-center mb-1">
          <label className="text-sm font-medium text-prompt-scene">Scene</label>
          <ComponentTooltip component="scene" />
        </div>
        <input
          type="text"
          value={scene.prompt.scene}
          onChange={(e) => handlePromptChange('scene', e.target.value)}
          className="input-field border-prompt-scene bg-background-dark"
          placeholder="Where is the scene taking place?"
        />
      </div>
      
      <div>
        <div className="flex items-center mb-1">
          <label className="text-sm font-medium text-prompt-motion">Motion</label>
          <ComponentTooltip component="motion" />
        </div>
        <input
          type="text"
          value={scene.prompt.motion}
          onChange={(e) => handlePromptChange('motion', e.target.value)}
          className="input-field border-prompt-motion bg-background-dark"
          placeholder="How is the subject moving?"
        />
      </div>
      
      <div>
        <div className="flex items-center mb-1">
          <label className="text-sm font-medium text-prompt-camera">Camera</label>
          <ComponentTooltip component="camera" />
        </div>
        <input
          type="text"
          value={scene.prompt.camera}
          onChange={(e) => handlePromptChange('camera', e.target.value)}
          className="input-field border-prompt-camera bg-background-dark"
          placeholder="How is the camera moving?"
        />
      </div>
      
      <div className="md:col-span-2">
        <div className="flex items-center mb-1">
          <label className="text-sm font-medium text-prompt-atmosphere">Atmosphere</label>
          <ComponentTooltip component="atmosphere" />
        </div>
        <input
          type="text"
          value={scene.prompt.atmosphere}
          onChange={(e) => handlePromptChange('atmosphere', e.target.value)}
          className="input-field border-prompt-atmosphere bg-background-dark"
          placeholder="What is the mood or atmosphere?"
        />
      </div>

      <div className="md:col-span-2">
        <div className="flex items-center mb-1">
          <label className="text-sm font-medium">Full Prompt</label>
          <ComponentTooltip component="full" />
        </div>
        <textarea
          value={scene.prompt.full}
          onChange={(e) => onUpdate({ prompt: { ...scene.prompt, full: e.target.value } })}
          className="input-field min-h-24 bg-background-dark"
          placeholder="Enter a complete prompt to override the component-based generation"
        />
        <p className="text-xs text-gray-400 mt-1">
          This will override the component-based prompt generation.
        </p>
      </div>
    </div>
  );
};

export default ComponentEditor;
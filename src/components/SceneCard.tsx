import React from 'react';
import { useAppStore } from '../store';
import { Scene } from '../types';
import PromptEditor from './PromptEditor';
import { Trash2, Plus, Minus, GripVertical } from 'lucide-react';

interface SceneCardProps {
  scene: Scene;
  index: number;
  onDragStart: (index: number) => void;
}

const SceneCard: React.FC<SceneCardProps> = ({ scene, index, onDragStart }) => {
  const { updateScene, removeScene, editMode, setEditMode } = useAppStore();

  const handleDurationChange = (change: number) => {
    const newDuration = Math.max(1, scene.duration + change);
    updateScene(scene.id, { duration: newDuration });
  };

  return (
    <div 
      className="scene-card" 
      draggable
      onDragStart={(e) => {
        onDragStart(index);
        // Set drag image to be a ghost of the element
        const ghostElement = e.currentTarget.cloneNode(true) as HTMLElement;
        ghostElement.style.position = 'absolute';
        ghostElement.style.top = '-1000px';
        ghostElement.style.opacity = '0.5';
        document.body.appendChild(ghostElement);
        e.dataTransfer.setDragImage(ghostElement, 20, 20);
        
        // Clean up the ghost element after drag ends
        setTimeout(() => {
          document.body.removeChild(ghostElement);
        }, 0);
      }}
    >
      <div className="scanline"></div>
      
      {/* Scene Header */}
      <div className="scene-header">
        <div className="flex items-center">
          <div 
            className="mr-2 cursor-move text-gray-400 hover:text-secondary-cyan"
            onMouseDown={() => onDragStart(index)}
          >
            <GripVertical size={20} />
          </div>
          <h3 className="text-xl font-orbitron text-secondary-cyan">Scene {index + 1}</h3>
        </div>
        <div className="flex items-center">
          <div className="flex items-center mr-4">
            <button
              onClick={() => handleDurationChange(-1)}
              className="w-8 h-8 flex items-center justify-center bg-background-dark hover:bg-ui-highlight transition-colors"
              disabled={scene.duration <= 1}
            >
              <Minus size={16} />
            </button>
            <span className="w-8 text-center font-orbitron">{scene.duration}s</span>
            <button
              onClick={() => handleDurationChange(1)}
              className="w-8 h-8 flex items-center justify-center bg-background-dark hover:bg-ui-highlight transition-colors"
            >
              <Plus size={16} />
            </button>
          </div>
          <button
            onClick={() => removeScene(scene.id)}
            className="w-8 h-8 flex items-center justify-center bg-background-dark hover:bg-red-900 transition-colors"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
      
      <div className="mt-4">
        {/* Prompt Editor */}
        <PromptEditor
          scene={scene}
          onUpdate={(updates) => updateScene(scene.id, updates)}
          editMode={editMode}
          onEditModeChange={setEditMode}
        />
        
        {/* Subtitle and Voiceover */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Subtitle</label>
            <input
              type="text"
              value={scene.subtitle}
              onChange={(e) => updateScene(scene.id, { subtitle: e.target.value })}
              className="input-field"
              placeholder="On-screen text (optional)"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Voiceover</label>
            <input
              type="text"
              value={scene.voiceover}
              onChange={(e) => updateScene(scene.id, { voiceover: e.target.value })}
              className="input-field"
              placeholder="Spoken text (optional)"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SceneCard;
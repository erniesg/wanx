import React, { useState } from 'react';
import { Scene } from '../../types';
import PromptText from './PromptText';
import ComponentEditor from './ComponentEditor';
import PromptComponentPopup from './PromptComponentPopup';
import { Edit, Code } from 'lucide-react';

interface PromptEditorProps {
  scene: Scene;
  onUpdate: (updates: Partial<Scene>) => void;
  editMode: 'interactive' | 'component';
  onEditModeChange: (mode: 'interactive' | 'component') => void;
  bgColor?: string;
}

const PromptEditor: React.FC<PromptEditorProps> = ({
  scene,
  onUpdate,
  editMode,
  onEditModeChange,
  bgColor = "background-dark"
}) => {
  const [activeComponent, setActiveComponent] = useState<string | null>(null);
  const [hoveredComponent, setHoveredComponent] = useState <string | null>(null);

  const handleComponentClick = (component: string) => {
    setActiveComponent(component);
  };

  const handleComponentSave = (value: string) => {
    if (activeComponent) {
      onUpdate({
        prompt: {
          ...scene.prompt,
          [activeComponent]: value
        }
      });
    }
  };

  const handleFullPromptChange = (value: string) => {
    onUpdate({
      prompt: {
        ...scene.prompt,
        full: value
      }
    });
  };

  return (
    <div className="mb-4">
      {editMode === 'interactive' ? (
        <PromptText
          prompt={scene.prompt}
          onComponentClick={handleComponentClick}
          highlightComponent={hoveredComponent}
          onFullPromptChange={handleFullPromptChange}
          bgColor={bgColor}
          onComponentHover={setHoveredComponent}
        />
      ) : (
        <ComponentEditor scene={scene} onUpdate={onUpdate} bgColor={bgColor} />
      )}

      {activeComponent && (
        <PromptComponentPopup
          component={activeComponent}
          value={scene.prompt[activeComponent as keyof typeof scene.prompt] as string}
          onSave={handleComponentSave}
          onClose={() => setActiveComponent(null)}
        />
      )}
    </div>
  );
};

export default PromptEditor;
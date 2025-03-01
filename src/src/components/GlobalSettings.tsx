import React, { useRef, useState } from 'react';
import { useAppStore } from '../store';
import { ATMOSPHERE_OPTIONS, STYLE_OPTIONS } from '../types';
import Dropdown from './common/Dropdown';
import { Upload, RefreshCw, Plus, GripVertical, Trash2, Edit, Code, ChevronDown, ChevronUp } from 'lucide-react';
import { motion } from 'framer-motion';
import ComponentTooltip from './PromptEditor/ComponentTooltip';
import PromptEditor from './PromptEditor';

const GlobalSettings: React.FC = () => {
  const { 
    globalSettings, 
    setGlobalSettings, 
    scenes, 
    setActiveScene,
    addScene,
    updateScene,
    removeScene,
    reorderScenes,
    editMode,
    setEditMode
  } = useAppStore();
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isGeneratingCover, setIsGeneratingCover] = useState(false);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const dragOverItemIndex = useRef<number | null>(null);
  const [expandedSceneId, setExpandedSceneId] = useState<string | null>(null);
  const [allExpanded, setAllExpanded] = useState(false);
  const [dropIndicatorPosition, setDropIndicatorPosition] = useState<number | null>(null);
  const [hoveredSceneId, setHoveredSceneId] = useState<string | null>(null);
  const [hoveredModeButton, setHoveredModeButton] = useState(false);

  const handleCoverImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const imageUrl = URL.createObjectURL(file);
      setGlobalSettings({ 
        coverImage: file,
        coverImageUrl: imageUrl
      });
    }
  };

  const triggerFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const generateAICoverImage = () => {
    setIsGeneratingCover(true);
    // Simulate AI image generation
    setTimeout(() => {
      const dummyImageUrl = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1964&auto=format&fit=crop";
      setGlobalSettings({
        coverImageUrl: dummyImageUrl
      });
      setIsGeneratingCover(false);
    }, 2000);
  };

  const handleCoverDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleCoverDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      const imageUrl = URL.createObjectURL(file);
      setGlobalSettings({ 
        coverImage: file,
        coverImageUrl: imageUrl
      });
    }
  };

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>, index: number) => {
    e.preventDefault();
    dragOverItemIndex.current = index;
    setDropIndicatorPosition(index);
  };

  const handleDragEnd = () => {
    if (draggedIndex !== null && dragOverItemIndex.current !== null && draggedIndex !== dragOverItemIndex.current) {
      reorderScenes(draggedIndex, dragOverItemIndex.current);
    }
    setDraggedIndex(null);
    dragOverItemIndex.current = null;
    setDropIndicatorPosition(null);
  };

  const toggleSceneExpansion = (sceneId: string) => {
    setExpandedSceneId(expandedSceneId === sceneId ? null : sceneId);
  };

  const toggleAllScenes = () => {
    if (allExpanded) {
      // Collapse all scenes
      setExpandedSceneId(null);
    } else {
      // Expand all scenes - we'll use the first scene ID as a marker
      setExpandedSceneId(scenes.length > 0 ? scenes[0].id : null);
    }
    setAllExpanded(!allExpanded);
  };

  return (
    <div className="cyberpunk-card p-6 mb-6">
      <div className="scanline"></div>
      <h2 className="text-xl font-orbitron mb-4 text-secondary-cyan">Script Review</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Cover Image */}
        <div className="relative h-full flex flex-col">
          <div 
            className="w-full aspect-[9/16] bg-background-dark flex items-center justify-center cursor-pointer overflow-hidden"
            style={{
              clipPath: 'polygon(0 10px, 10px 0, calc(100% - 10px) 0, 100% 10px, 100% calc(100% - 10px), calc(100% - 10px) 100%, 10px 100%, 0 calc(100% - 10px))'
            }}
            onClick={triggerFileInput}
            onDragOver={handleCoverDragOver}
            onDrop={handleCoverDrop}
          >
            {isGeneratingCover ? (
              <div className="flex flex-col items-center text-gray-400">
                <div className="w-8 h-8 border-2 border-secondary-cyan border-t-transparent rounded-full animate-spin mb-2"></div>
                <span>Generating cover...</span>
              </div>
            ) : globalSettings.coverImageUrl ? (
              <div className="relative w-full h-full group">
                <img 
                  src={globalSettings.coverImageUrl} 
                  alt="Cover" 
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-black bg-opacity-50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                  <span className="text-white">Click to change or drop image here</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center text-gray-400">
                <Upload size={32} />
                <span className="mt-2">Upload Cover Image</span>
                <span className="text-xs mt-1">or drag and drop</span>
              </div>
            )}
          </div>
          
          {globalSettings.coverImageUrl && (
            <div className="absolute top-2 right-2 bg-primary-magenta text-white text-xs px-2 py-1 rounded-sm">
              AI Generated
            </div>
          )}
          
          <div className="flex mt-2 space-x-2">
            <button 
              className="flex-1 text-sm py-1 bg-ui-card hover:bg-ui-highlight transition-colors flex items-center justify-center"
              onClick={triggerFileInput}
            >
              <Upload size={14} className="mr-1" />
              Upload
            </button>
            <button 
              className="flex-1 text-sm py-1 bg-ui-card hover:bg-ui-highlight transition-colors flex items-center justify-center"
              onClick={generateAICoverImage}
              disabled={isGeneratingCover}
            >
              <RefreshCw size={14} className="mr-1" />
              Generate AI Cover
            </button>
          </div>
          
          <input 
            type="file" 
            ref={fileInputRef}
            onChange={handleCoverImageChange}
            accept="image/*"
            className="hidden"
          />
        </div>
        
        {/* Title and Dropdowns */}
        <div className="md:col-span-2 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Video Title</label>
            <input
              type="text"
              value={globalSettings.title}
              onChange={(e) => setGlobalSettings({ title: e.target.value })}
              className="input-field bg-background-dark"
              placeholder="Enter video title"
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="relative">
              <div className="flex items-center mb-1">
                <label className="block text-sm font-medium">Atmosphere</label>
                <ComponentTooltip component="atmosphere" />
              </div>
              <Dropdown
                options={ATMOSPHERE_OPTIONS}
                value={globalSettings.atmosphere}
                onChange={(value) => setGlobalSettings({ atmosphere: value })}
                allowCustom
                searchable
                placeholder="Select or enter atmosphere"
              />
            </div>
            
            <div className="relative">
              <div className="flex items-center mb-1">
                <label className="block text-sm font-medium">Style</label>
                <ComponentTooltip component="style" />
              </div>
              <Dropdown
                options={STYLE_OPTIONS}
                value={globalSettings.style}
                onChange={(value) => setGlobalSettings({ style: value })}
                allowCustom
                searchable
                placeholder="Select or enter style"
              />
            </div>
          </div>
          
          {/* Total Scenes */}
          <div className="mt-4">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-medium text-secondary-cyan">Total Scenes</h3>
              <div className="flex items-center">
                <span className="font-orbitron">
                  <span className="text-secondary-cyan">{scenes.length}</span>
                  <span className="text-gray-400">/3</span>
                </span>
              </div>
            </div>
          </div>
          
          {/* Scenes Section */}
          <div className="mt-4">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-medium text-secondary-cyan">Scenes</h3>
              <div className="flex space-x-2">
                <button 
                  onClick={toggleAllScenes}
                  className="neon-button flex items-center py-1 px-3 text-xs"
                >
                  {allExpanded ? (
                    <>
                      <ChevronUp size={14} className="mr-1" />
                      Collapse All
                    </>
                  ) : (
                    <>
                      <ChevronDown size={14} className="mr-1" />
                      Expand All
                    </>
                  )}
                </button>
                <button 
                  onClick={addScene}
                  className="neon-button flex items-center py-1 px-3 text-xs"
                  disabled={scenes.length >= 3}
                >
                  <Plus size={14} className="mr-1" />
                  Add Scene
                </button>
              </div>
            </div>
            
            <div className="space-y-2 relative">
              {/* Drop indicator line */}
              {dropIndicatorPosition !== null && (
                <div 
                  className="drag-indicator"
                  style={{ 
                    top: dropIndicatorPosition === 0 ? '0' : `calc(${dropIndicatorPosition * 100}% - 1px)`,
                    transform: 'translateY(-50%)'
                  }}
                />
              )}
              
              {scenes.map((scene, index) => {
                const isExpanded = expandedSceneId === scene.id || allExpanded;
                const isDragging = draggedIndex === index;
                const isHovered = hoveredSceneId === scene.id;
                
                return (
                  <div 
                    key={scene.id}
                    className={`transition-all duration-200 ${isDragging ? 'opacity-50' : ''}`}
                    onDragOver={(e) => handleDragOver(e, index)}
                    onDragEnd={handleDragEnd}
                    draggable
                    onDragStart={() => handleDragStart(index)}
                    onMouseEnter={() => setHoveredSceneId(scene.id)}
                    onMouseLeave={() => setHoveredSceneId(null)}
                  >
                    <div className={`${isDragging ? 'dragging' : ''}`}>
                      <div 
                        className={`cyberpunk-card p-2 cursor-pointer transition-colors ${
                          isHovered || isDragging ? 'bg-ui-highlight/10' : ''
                        }`}
                        onClick={() => toggleSceneExpansion(scene.id)}
                      >
                        <div className="scanline"></div>
                        <div className="flex items-start">
                          {/* Fixed number */}
                          <div className="flex-shrink-0 w-8 h-8 bg-ui-highlight/20 rounded-full flex items-center justify-center mr-3 text-secondary-cyan font-orbitron">
                            {index + 1}
                          </div>
                          
                          {/* Editable prompt display */}
                          <div className="flex-grow">
                            <div 
                              className="text-xs text-gray-300 p-2 bg-background-dark border border-gray-700 rounded-sm cursor-text hover:border-secondary-cyan transition-colors"
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleSceneExpansion(scene.id);
                              }}
                            >
                              {scene.prompt.full || `${scene.prompt.subject} ${scene.prompt.scene}, ${scene.prompt.motion}, ${scene.prompt.camera}, ${scene.prompt.atmosphere} atmosphere`}
                            </div>
                            <div className="flex justify-between items-center mt-1">
                              <div className="flex items-center">
                                <div className="text-xs text-gray-400">Scene {index + 1}</div>
                              </div>
                              <div className="flex items-center">
                                <div className="cursor-move text-gray-400 hover:text-secondary-cyan mr-2">
                                  <GripVertical size={14} />
                                </div>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    removeScene(scene.id);
                                  }}
                                  className="w-6 h-6 flex items-center justify-center bg-background-dark hover:bg-red-900 transition-colors"
                                  disabled={scenes.length <= 1}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      {/* Expanded scene details */}
                      {isExpanded && (
                        <div className={`mt-2 ${isHovered || isDragging ? 'bg-ui-highlight/10' : 'bg-ui-card'} rounded-sm border border-gray-700`}>
                          <div className="p-4">
                            <div className="flex justify-between items-center mb-4">
                              <h3 className="text-lg font-medium text-secondary-cyan">Video Prompt</h3>
                              {editMode === 'interactive' ? (
                                <button
                                  onClick={() => setEditMode('component')}
                                  onMouseEnter={() => setHoveredModeButton(true)}
                                  onMouseLeave={() => setHoveredModeButton(false)}
                                  className="flex items-center text-xs px-3 py-1 rounded-sm transition-colors bg-background-dark border border-gray-700 hover:bg-secondary-cyan hover:text-background-dark hover:border-secondary-cyan"
                                >
                                  <Code size={14} className="mr-1" /> Advanced Mode
                                </button>
                              ) : (
                                <button
                                  onClick={() => setEditMode('interactive')}
                                  onMouseEnter={() => setHoveredModeButton(true)}
                                  onMouseLeave={() => setHoveredModeButton(false)}
                                  className="flex items-center text-xs px-3 py-1 rounded-sm transition-colors bg-background-dark border border-gray-700 hover:bg-secondary-cyan hover:text-background-dark hover:border-secondary-cyan"
                                >
                                  <Edit size={14} className="mr-1" /> Interactive Mode
                                </button>
                              )}
                            </div>
                            
                            <PromptEditor
                              scene={scene}
                              onUpdate={(updates) => updateScene(scene.id, updates)}
                              editMode={editMode}
                              onEditModeChange={setEditMode}
                              bgColor="background-dark"
                            />
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                              <div>
                                <label className="block text-sm font-medium mb-1">Subtitle</label>
                                <input
                                  type="text"
                                  value={scene.subtitle}
                                  onChange={(e) => updateScene(scene.id, { subtitle: e.target.value })}
                                  className="input-field bg-background-dark"
                                  placeholder="On-screen text (optional)"
                                />
                              </div>
                              
                              <div>
                                <label className="block text-sm font-medium mb-1">Voiceover</label>
                                <input
                                  type="text"
                                  value={scene.voiceover}
                                  onChange={(e) => updateScene(scene.id, { voiceover: e.target.value })}
                                  className="input-field bg-background-dark"
                                  placeholder="Spoken text (optional)"
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GlobalSettings;
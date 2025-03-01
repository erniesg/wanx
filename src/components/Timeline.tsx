import React from 'react';
import { useAppStore } from '../store';
import { motion } from 'framer-motion';
import { Clock } from 'lucide-react';

const Timeline: React.FC = () => {
  const { scenes, totalDuration, setActiveScene } = useAppStore();
  const maxDuration = 22; // Maximum allowed duration in seconds
  const durationPercentage = (totalDuration / maxDuration) * 100;
  const isWarning = totalDuration > maxDuration * 0.8;
  
  // Calculate positions for each scene
  let currentPosition = 0;
  const scenePositions = scenes.map(scene => {
    const width = (scene.duration / maxDuration) * 100;
    const position = currentPosition;
    currentPosition += width;
    return { id: scene.id, width, position };
  });

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-lg font-medium text-secondary-cyan">Timeline</h3>
        <div className="flex items-center">
          <Clock className="text-secondary-cyan mr-2" size={18} />
          <span className="font-orbitron">
            <span className={isWarning ? 'text-red-500' : 'text-secondary-cyan'}>
              {totalDuration}
            </span>
            <span className="text-gray-400">/{maxDuration}s</span>
          </span>
        </div>
      </div>
      
      <div className="cyberpunk-card timeline-container h-6 relative">
        <div className="scanline"></div>
        
        {/* Scene blocks */}
        {scenePositions.map((scene, index) => (
          <motion.div
            key={scene.id}
            className="timeline-scene hover:opacity-100 cursor-pointer"
            style={{ 
              left: `${scene.position}%`, 
              width: `${scene.width}%`,
              background: `linear-gradient(135deg, hsl(${index * 40}, 100%, 50%), hsl(${index * 40 + 30}, 100%, 50%))`
            }}
            whileHover={{ y: -2 }}
            onClick={() => setActiveScene(scene.id)}
          />
        ))}
        
        {/* Time markers with improved positioning */}
        <div className="absolute bottom-0 left-2 text-xs text-gray-400">0s</div>
        <div className="absolute bottom-0 right-2 text-xs text-gray-400">{maxDuration}s</div>
      </div>
    </div>
  );
};

export default Timeline;
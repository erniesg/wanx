export interface Scene {
  id: string;
  duration: number;
  referenceImage?: File | null;
  referenceImageUrl?: string;
  prompt: {
    subject: string;
    scene: string;
    motion: string;
    camera: string;
    atmosphere: string;
    full: string;
  };
  subtitle: string;
  voiceover: string;
  motionPreset: string;
  cameraPreset: string;
}

export interface GlobalSettings {
  title: string;
  coverImage?: File | null;
  coverImageUrl?: string;
  atmosphere: string;
  style: string;
}

export interface AppState {
  globalSettings: GlobalSettings;
  scenes: Scene[];
  totalDuration: number;
  activeSceneId: string | null;
  editMode: 'interactive' | 'component';
  activePromptComponent: string | null;
  currentPage: 'landing' | 'script' | 'processing' | 'completion';
  inputType: 'url' | 'text';
  inputValue: string;
  processingStatus: {
    step: 'analyzing' | 'generating' | 'rendering' | 'complete';
    progress: number;
    message: string;
  };
  videoUrl: string;
  
  // Actions
  setGlobalSettings: (settings: Partial<GlobalSettings>) => void;
  addScene: () => void;
  updateScene: (id: string, updates: Partial<Scene>) => void;
  removeScene: (id: string) => void;
  reorderScenes: (startIndex: number, endIndex: number) => void;
  setActiveScene: (id: string | null) => void;
  setEditMode: (mode: 'interactive' | 'component') => void;
  setActivePromptComponent: (component: string | null) => void;
  calculateTotalDuration: () => void;
  setCurrentPage: (page: 'landing' | 'script' | 'processing' | 'completion') => void;
  setInputType: (type: 'url' | 'text') => void;
  setInputValue: (value: string) => void;
  startGeneration: () => void;
  generateVideo: () => void;
  publishToTikTok: () => Promise<boolean>;
}

export interface DropdownOption {
  value: string;
  label: string;
}

export interface ComponentGuide {
  title: string;
  tooltip: string;
  description: string;
  recommendations: string[];
  examples: string[];
}

export const COMPONENT_GUIDES: Record<string, ComponentGuide> = {
  subject: {
    title: "Subject (主体)",
    tooltip: "The main focus or character in your video",
    description: "This defines what viewers primarily see and follow throughout the generation. Can include people, animals, plants, objects, characters, entities, or concepts that serve as the visual anchor.",
    recommendations: [
      "Be specific about appearance details (clothing, age, features)",
      "For humans, specify posture, expression, and distinguishing traits",
      "For objects, describe material, size, and distinctive characteristics",
      "Mention multiple subjects if there's interaction between them",
      "Use adjectives that convey the subject's nature (majestic mountain, playful cat)"
    ],
    examples: [
      "一位身穿蓝色汉服的年轻女子 (A young woman wearing blue Hanfu)",
      "一只橙色的猫咪戴着飞行员护目镜 (An orange cat wearing aviator goggles)",
      "古老的石头雕像，表面布满青苔和裂纹 (An ancient stone statue covered with moss and cracks)"
    ]
  },
  scene: {
    title: "Scene (场景)",
    tooltip: "The environment or setting surrounding your subject",
    description: "This establishes context, spatial relationships, and background elements. Can include location, background, foreground, physical space, weather conditions, time of day, or environmental context.",
    recommendations: [
      "Establish the type of location (indoor/outdoor, urban/natural)",
      "Include atmospheric elements (weather, time of day, season)",
      "Describe notable background elements or landmarks",
      "Consider lighting conditions that define the space",
      "Specify the relationship between subject and environment"
    ],
    examples: [
      "在晨雾笼罩的竹林中 (In a bamboo forest shrouded in morning mist)",
      "繁忙的城市街道，霓虹灯在雨后的地面上反射 (Busy city street with neon lights reflecting on the ground after rain)",
      "古老图书馆内，阳光透过彩色玻璃窗撒落在书架上 (Inside an ancient library, sunlight falls on bookshelves through colored glass windows)"
    ]
  },
  motion: {
    title: "Motion (运动)",
    tooltip: "How elements change or move throughout the video",
    description: "This creates dynamism and temporal progression in the scene. Can include stationary poses, small movements, large actions, transformations, or state changes over time.",
    recommendations: [
      "Describe the direction and speed of movement",
      "Include secondary motion elements (hair flowing, clothes rippling)",
      "Specify if motion is continuous or happens in stages",
      "Mention how different elements interact through movement",
      "Consider physical properties (weight, fluidity, rigidity) that affect motion"
    ],
    examples: [
      "缓缓转身面向镜头，长发在风中飘扬 (Slowly turning to face the camera, long hair flowing in the wind)",
      "从蓓蕾到盛开的过程，花瓣舒展开来 (From bud to bloom, petals unfurling)",
      "水珠沿着叶片表面滚动，最终滴落 (Water droplets rolling along the leaf surface, eventually falling)"
    ]
  },
  camera: {
    title: "Camera (镜头)",
    tooltip: "How the video is framed and filmed",
    description: "This guides viewer attention and creates the visual storytelling approach. Can include camera angle, movement patterns, focus adjustments, perspective shifts, and framing techniques.",
    recommendations: [
      "Specify the starting distance (close-up, medium shot, wide shot)",
      "Describe any camera movement (panning, zooming, tracking)",
      "Mention focus changes or focus depth",
      "Consider unique perspectives (bird's eye, worm's eye, dutch angle)",
      "Indicate if the camera reveals information in a specific sequence"
    ],
    examples: [
      "镜头缓缓拉远，展现整个城市的全景 (Camera slowly zooms out to reveal the panorama of the entire city)",
      "镜头环绕主体旋转，捕捉每个角度的细节 (Camera orbits around the subject, capturing details from every angle)",
      "镜头从低角度仰拍，强调主体的高大威严 (Camera shoots from a low angle upward, emphasizing the subject's imposing stature)"
    ]
  },
  atmosphere: {
    title: "Atmosphere (氛围)",
    tooltip: "The mood, feeling, and emotional quality that permeates the video",
    description: "This establishes how viewers should emotionally respond. Can include emotional qualities, sensory impressions, psychological states, and tonal aspects.",
    recommendations: [
      "Use evocative adjectives that convey feeling states",
      "Consider contrasting emotions for dynamic atmosphere",
      "Describe sensory qualities beyond just visuals (implied sound, texture)",
      "Think about the psychological impact on viewers",
      "Use metaphorical language to enhance mood description"
    ],
    examples: [
      "神秘而宁静，仿佛时间已经停滞 (Mysterious and tranquil, as if time has stopped)",
      "充满活力与希望，阳光普照的喜悦感 (Full of vitality and hope, the joy of sunshine)",
      "压抑而紧张，即将爆发的暴风雨前的宁静 (Oppressive and tense, the calm before an impending storm)"
    ]
  },
  style: {
    title: "Style (风格)",
    tooltip: "The visual treatment and artistic approach applied to the video",
    description: "This determines aesthetic quality and visual language. Can include artistic references, color treatments, rendering techniques, lighting approaches, and genre conventions.",
    recommendations: [
      "Reference specific art styles or creators when appropriate",
      "Describe color palette and saturation preferences",
      "Specify lighting quality (harsh, soft, dramatic, diffused)",
      "Mention texture and detail level (painterly, photorealistic)",
      "Consider era or genre-specific visual treatments"
    ],
    examples: [
      "日本浮世绘风格，线条清晰，色彩平面化 (Japanese ukiyo-e style with clear outlines and flat colors)",
      "复古电影质感，略带颗粒感和温暖的色调 (Vintage film quality with slight grain and warm tones)",
      "赛博朋克风格，霓虹色彩与强烈的明暗对比 (Cyberpunk style with neon colors and strong contrast)"
    ]
  },
  full: {
    title: "Full Prompt (完整提示)",
    tooltip: "The complete prompt that integrates all components",
    description: "This is the comprehensive prompt that combines all individual components into a flowing, natural description. It can be manually edited for fine-tuning or generated automatically from the components.",
    recommendations: [
      "Ensure all components flow naturally together",
      "Add connecting words and phrases for readability",
      "Maintain consistent tone and style throughout",
      "Consider the order of information for logical flow",
      "Read aloud to check for natural language patterns"
    ],
    examples: [
      "一位穿着红色旗袍的年轻女子站在雨中的上海外滩，背景是灯火辉煌的夜景。她缓缓撑起一把透明雨伞，雨滴落在伞面上形成涟漪，旗袍上的水珠闪烁着城市的光芒。镜头从特写慢慢拉远，环绕她旋转一周，展现出整个雨中都市的氛围。画面带着一种怀旧而忧郁的气质，仿佛一段逝去的回忆。整体呈现电影般的质感，偏冷色调，有如王家卫电影的视觉风格。 (A young woman in a red qipao standing in the rain on Shanghai's Bund, with the brilliantly lit night scene as background. She slowly opens a transparent umbrella, with raindrops forming ripples on its surface, and water droplets on her qipao reflecting the city lights. The camera slowly pulls back from a close-up, rotating around her once to reveal the entire rainy urban atmosphere. The scene carries a nostalgic yet melancholic quality, like a fading memory. The overall presentation has a cinematic texture with cool color tones, resembling Wong Kar-wai's visual style.)"
    ]
  }
};

export const ATMOSPHERE_OPTIONS: DropdownOption[] = [
  { value: 'lively', label: 'Lively/Joyful' },
  { value: 'peaceful', label: 'Peaceful/Serene' },
  { value: 'energetic', label: 'Energetic/Dynamic' },
  { value: 'mysterious', label: 'Mysterious/Intriguing' },
  { value: 'cybernetic', label: 'Cybernetic/Futuristic' },
  { value: 'nostalgic', label: 'Nostalgic/Retro' },
  { value: 'dreamy', label: 'Dreamy/Ethereal' },
  { value: 'dramatic', label: 'Dramatic/Intense' },
  { value: 'melancholic', label: 'Melancholic/Somber' },
  { value: 'whimsical', label: 'Whimsical/Playful' },
  { value: 'romantic', label: 'Romantic/Intimate' },
  { value: 'suspenseful', label: 'Suspenseful/Tense' }
];

export const STYLE_OPTIONS: DropdownOption[] = [
  { value: 'modern', label: 'Modern Cinematic' },
  { value: 'minimalist', label: 'Clean Minimalist' },
  { value: 'vibrant', label: 'Vibrant Pop' },
  { value: 'tech', label: 'Tech Futuristic' },
  { value: 'cyberpunk', label: 'Cyberpunk' },
  { value: 'neon', label: 'Neon City' },
  { value: 'film-noir', label: 'Film Noir' },
  { value: 'anime', label: 'Anime Style' },
  { value: 'watercolor', label: 'Watercolor Painting' },
  { value: 'retro-80s', label: 'Retro 80s' },
  { value: 'vaporwave', label: 'Vaporwave Aesthetic' },
  { value: 'documentary', label: 'Documentary Style' },
  { value: 'fantasy', label: 'Fantasy Realm' },
  { value: 'vintage-film', label: 'Vintage Film Grain' }
];

export const CAMERA_OPTIONS: DropdownOption[] = [
  { value: 'zoom-out', label: 'Zoom Out: Camera gradually zooming out to reveal...' },
  { value: 'zoom-in', label: 'Zoom In: Camera zooming in to focus on details...' },
  { value: 'pan-left-right', label: 'Pan Left to Right: Camera smoothly moving from left to right...' },
  { value: 'pan-right-left', label: 'Pan Right to Left: Camera smoothly moving from right to left...' },
  { value: 'follow', label: 'Follow: Camera following the subject through...' },
  { value: 'orbit', label: 'Orbit: Camera circling around the subject...' },
  { value: 'stationary', label: 'Stationary: Fixed camera capturing the scene...' },
  { value: 'tracking', label: 'Tracking Shot: Camera moving alongside the subject...' },
  { value: 'dutch-angle', label: 'Dutch Angle: Camera tilted for a dynamic perspective...' }
];

export const MOTION_OPTIONS: DropdownOption[] = [
  { value: 'natural', label: 'Natural Movement: Realistic human/object movement' },
  { value: 'smooth-writing', label: 'Smooth Writing: Hand gracefully writing with flowing motion' },
  { value: 'floating', label: 'Floating: Gentle hovering or drifting movement' },
  { value: 'energetic', label: 'Energetic: Quick, dynamic movement with vigor' },
  { value: 'slow-motion', label: 'Slow Motion: Deliberate slow-motion effect' },
  { value: 'time-lapse', label: 'Time Lapse: Accelerated passage of time' },
  { value: 'particle', label: 'Particle Effect: Elements dissolving/forming in particles' },
  { value: 'ripple', label: 'Ripple: Wave-like movement spreading outward' },
  { value: 'transformation', label: 'Transformation: Object/character morphing into another form' }
];
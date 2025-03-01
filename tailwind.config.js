/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          magenta: '#ff00ff',
          purple: '#8a2be2',
        },
        secondary: {
          cyan: '#00ffff',
          green: '#39ff14',
        },
        background: {
          dark: '#0f0f1a',
          darker: '#1a1a2e',
        },
        ui: {
          card: '#2d2d44',
          highlight: '#ff00ff80',
        },
        prompt: {
          subject: '#ff00ff',
          scene: '#00ffff',
          motion: '#39ff14',
          camera: '#ffaa00',
          atmosphere: '#0080ff',
        }
      },
      fontFamily: {
        'orbitron': ['Orbitron', 'sans-serif'],
        'rajdhani': ['Rajdhani', 'sans-serif'],
        'syncopate': ['Syncopate', 'sans-serif'],
      },
      animation: {
        'glitch': 'glitch 1s linear infinite',
        'scanline': 'scanline 8s linear infinite',
      },
      keyframes: {
        glitch: {
          '0%, 100%': { transform: 'translate(0)' },
          '20%': { transform: 'translate(-2px, 2px)' },
          '40%': { transform: 'translate(-2px, -2px)' },
          '60%': { transform: 'translate(2px, 2px)' },
          '80%': { transform: 'translate(2px, -2px)' },
        },
        scanline: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        }
      },
      backgroundImage: {
        'cyberpunk-grid': 'linear-gradient(to right, #1a1a2e 1px, transparent 1px), linear-gradient(to bottom, #1a1a2e 1px, transparent 1px)',
        'gradient-primary': 'linear-gradient(135deg, #ff00ff 0%, #8a2be2 100%)',
      },
      backgroundSize: {
        'grid': '20px 20px',
      },
    },
  },
  plugins: [],
};
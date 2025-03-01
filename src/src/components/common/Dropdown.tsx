import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { DropdownOption } from '../../types';
import { createPortal } from 'react-dom';

interface DropdownProps {
  options: DropdownOption[];
  value: string;
  onChange: (value: string) => void;
  allowCustom?: boolean;
  searchable?: boolean;
  placeholder?: string;
}

const Dropdown: React.FC<DropdownProps> = ({
  options,
  value,
  onChange,
  allowCustom = false,
  searchable = false,
  placeholder = 'Select an option'
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [customValue, setCustomValue] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0, width: 0 });

  // Find the selected option label
  const selectedOption = options.find(option => option.value === value);
  const displayValue = selectedOption ? selectedOption.label : value || placeholder;

  // Filter options based on search term
  const filteredOptions = options.filter(option => 
    option.label.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Update menu position when dropdown opens
  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const spaceBelow = viewportHeight - rect.bottom;
      const spaceNeeded = (filteredOptions.length * 36) + (searchable ? 60 : 0) + (allowCustom ? 60 : 0);
      
      // Determine if dropdown should open upward or downward
      const openUpward = spaceBelow < spaceNeeded && rect.top > spaceNeeded;
      
      setMenuPosition({
        top: openUpward ? rect.top - spaceNeeded : rect.bottom,
        left: rect.left,
        width: rect.width
      });
    }
  }, [isOpen, filteredOptions.length, searchable, allowCustom]);

  // Handle click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node) &&
          menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (isOpen && buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        setMenuPosition({
          top: rect.bottom,
          left: rect.left,
          width: rect.width
        });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [isOpen]);

  // Handle scroll events to reposition dropdown
  useEffect(() => {
    const handleScroll = () => {
      if (isOpen && buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        setMenuPosition({
          top: rect.bottom,
          left: rect.left,
          width: rect.width
        });
      }
    };

    window.addEventListener('scroll', handleScroll, true);
    return () => {
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [isOpen]);

  const handleOptionSelect = (option: DropdownOption) => {
    onChange(option.value);
    setIsOpen(false);
    setSearchTerm('');
  };

  const handleCustomValueSubmit = () => {
    if (customValue.trim()) {
      onChange(customValue);
      setIsOpen(false);
      setCustomValue('');
      setSearchTerm('');
    }
  };

  return (
    <div className="dropdown-container" ref={dropdownRef}>
      <button
        type="button"
        className="dropdown-button"
        onClick={() => setIsOpen(!isOpen)}
        ref={buttonRef}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <span className="truncate">{displayValue}</span>
        <ChevronDown 
          size={16} 
          className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} 
        />
      </button>

      {isOpen && createPortal(
        <div 
          className="dropdown-menu-portal"
          style={{
            position: 'fixed',
            top: `${menuPosition.top}px`,
            left: `${menuPosition.left}px`,
            width: `${menuPosition.width}px`,
            zIndex: 9999
          }}
          ref={menuRef}
          role="listbox"
        >
          {searchable && (
            <div className="p-2 border-b border-gray-700">
              <div className="relative">
                <Search size={16} className="absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-8 pr-2 py-1 bg-background-dark border border-gray-700 focus:outline-none focus:border-secondary-cyan"
                  placeholder="Search..."
                  autoFocus
                />
              </div>
            </div>
          )}

          <div className="max-h-60 overflow-y-auto">
            {filteredOptions.map((option) => (
              <div
                key={option.value}
                className="dropdown-item"
                onClick={() => handleOptionSelect(option)}
                role="option"
                aria-selected={option.value === value}
              >
                {option.label}
              </div>
            ))}

            {allowCustom && (
              <div className="p-2 border-t border-gray-700">
                <div className="flex">
                  <input
                    type="text"
                    value={customValue}
                    onChange={(e) => setCustomValue(e.target.value)}
                    className="flex-1 px-2 py-1 bg-background-dark border border-gray-700 focus:outline-none focus:border-secondary-cyan"
                    placeholder="Custom value..."
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleCustomValueSubmit();
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleCustomValueSubmit}
                    className="ml-2 px-2 py-1 bg-secondary-cyan text-background-dark font-medium"
                  >
                    Add
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

export default Dropdown;
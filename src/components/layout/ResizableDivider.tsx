/**
 * ResizableDivider — draggable divider between panels
 * Allows user to resize left/right panels by dragging
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';

interface ResizableDividerProps {
  onResize: (delta: number) => void;
  direction?: 'horizontal' | 'vertical';
}

export const ResizableDivider: React.FC<ResizableDividerProps> = ({ onResize, direction = 'horizontal' }) => {
  const [isDragging, setIsDragging] = useState(false);
  const startPos = useRef(0);
  const lastDelta = useRef(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startPos.current = direction === 'horizontal' ? e.clientX : e.clientY;
    lastDelta.current = 0;
  }, [direction]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const currentPos = direction === 'horizontal' ? e.clientX : e.clientY;
      const delta = currentPos - startPos.current;
      const incrementalDelta = delta - lastDelta.current;
      lastDelta.current = delta;
      onResize(incrementalDelta);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging, direction, onResize]);

  return (
    <div
      className={`resizable-divider ${isDragging ? 'dragging' : ''}`}
      onMouseDown={handleMouseDown}
      style={direction === 'vertical' ? { width: '100%', height: 4, cursor: 'row-resize' } : {}}
    />
  );
};

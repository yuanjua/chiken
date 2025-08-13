"use client";

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';

interface BubbleToastProps {
  message: string;
  show: boolean;
  variant?: 'default' | 'destructive';
  className?: string;
}

export function BubbleToast({ 
  message, 
  show, 
  variant = 'default',
  className 
}: BubbleToastProps) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ 
            duration: 0.3,
            ease: "easeOut"
          }}
          className={cn(
            "fixed bottom-12 left-1/2 transform -translate-x-1/2 text-sm rounded-lg px-4 py-2 shadow-lg z-50",
            variant === 'destructive' 
              ? "bg-red-500 text-white" 
              : "bg-gray-300 text-black",
            className
          )}
        >
          <div className='w-48 text-center'>{message}</div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default BubbleToast;

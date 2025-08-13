import React from "react";
import { Dot, PencilLine } from "lucide-react";

const AiGenerating = () => {
  return (
    <div className="flex items-center space-x-1 h-6 animate-pulse">
      <PencilLine size={20} className="text-gray-500 dark:text-gray-400" />
      <Dot
        size={20}
        className="text-gray-500 dark:text-gray-400 animate-bounce"
        style={{ animationDelay: "0ms", animationDuration: "1.4s" }}
      />
      <Dot
        size={20}
        className="text-gray-500 dark:text-gray-400 animate-bounce"
        style={{ animationDelay: "0.2s", animationDuration: "1.4s" }}
      />
      <Dot
        size={20}
        className="text-gray-500 dark:text-gray-400 animate-bounce"
        style={{ animationDelay: "0.4s", animationDuration: "1.4s" }}
      />
    </div>
  );
};

export default AiGenerating;

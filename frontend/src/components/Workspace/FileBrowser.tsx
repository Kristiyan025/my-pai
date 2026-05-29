import React from "react";
import { FileItem } from "@/lib/api";
import {
  FolderIcon,
  DocumentIcon,
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  FilmIcon,
  CodeBracketIcon,
  ArchiveBoxIcon,
  ArrowLeftIcon,
} from "@heroicons/react/24/outline";

interface FileBrowserProps {
  files: FileItem[];
  currentPath: string;
  selectedFile: string | null;
  onNavigate: (path: string) => void;
  onSelect: (file: FileItem) => void;
  onDoubleClick: (file: FileItem) => void;
}

const getFileIcon = (file: FileItem) => {
  if (file.type === "directory") {
    return FolderIcon;
  }

  const ext = file.name.split(".").pop()?.toLowerCase() || "";

  const iconMap: Record<string, any> = {
    txt: DocumentTextIcon,
    md: DocumentTextIcon,
    pdf: DocumentTextIcon,
    doc: DocumentTextIcon,
    docx: DocumentTextIcon,
    png: PhotoIcon,
    jpg: PhotoIcon,
    jpeg: PhotoIcon,
    gif: PhotoIcon,
    webp: PhotoIcon,
    svg: PhotoIcon,
    mp3: MusicalNoteIcon,
    wav: MusicalNoteIcon,
    flac: MusicalNoteIcon,
    ogg: MusicalNoteIcon,
    mp4: FilmIcon,
    mkv: FilmIcon,
    avi: FilmIcon,
    mov: FilmIcon,
    js: CodeBracketIcon,
    ts: CodeBracketIcon,
    jsx: CodeBracketIcon,
    tsx: CodeBracketIcon,
    py: CodeBracketIcon,
    java: CodeBracketIcon,
    c: CodeBracketIcon,
    cpp: CodeBracketIcon,
    h: CodeBracketIcon,
    rs: CodeBracketIcon,
    go: CodeBracketIcon,
    html: CodeBracketIcon,
    css: CodeBracketIcon,
    json: CodeBracketIcon,
    xml: CodeBracketIcon,
    yaml: CodeBracketIcon,
    yml: CodeBracketIcon,
    zip: ArchiveBoxIcon,
    tar: ArchiveBoxIcon,
    gz: ArchiveBoxIcon,
    rar: ArchiveBoxIcon,
    "7z": ArchiveBoxIcon,
  };

  return iconMap[ext] || DocumentIcon;
};

const formatFileSize = (bytes?: number) => {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i++;
  }
  return `${size.toFixed(1)} ${units[i]}`;
};

export default function FileBrowser({
  files,
  currentPath,
  selectedFile,
  onNavigate,
  onSelect,
  onDoubleClick,
}: FileBrowserProps) {
  const canGoUp = currentPath !== "/";

  const handleGoUp = () => {
    const parts = currentPath.split("/").filter(Boolean);
    parts.pop();
    onNavigate("/" + parts.join("/"));
  };

  const sortedFiles = [...files].sort((a, b) => {
    if (a.type !== b.type) {
      return a.type === "directory" ? -1 : 1;
    }
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-pai-accent flex items-center gap-2">
        {canGoUp && (
          <button
            onClick={handleGoUp}
            className="p-1 hover:bg-pai-accent rounded transition-colors"
            title="Go up"
          >
            <ArrowLeftIcon className="w-4 h-4" />
          </button>
        )}
        <div className="flex items-center gap-1 text-sm">
          <button
            onClick={() => onNavigate("/")}
            className="hover:text-pai-highlight transition-colors"
          >
            Home
          </button>
          {currentPath
            .split("/")
            .filter(Boolean)
            .map((part, index, arr) => {
              const path = "/" + arr.slice(0, index + 1).join("/");
              return (
                <React.Fragment key={path}>
                  <span className="text-pai-muted">/</span>
                  <button
                    onClick={() => onNavigate(path)}
                    className="hover:text-pai-highlight transition-colors"
                  >
                    {part}
                  </button>
                </React.Fragment>
              );
            })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {files.length === 0 ? (
          <div className="text-center py-12 text-pai-muted">
            <FolderIcon className="w-16 h-16 mx-auto mb-2 opacity-50" />
            <p>This folder is empty</p>
          </div>
        ) : (
          <div className="space-y-1">
            {sortedFiles.map((file) => {
              const Icon = getFileIcon(file);
              const isSelected = selectedFile === file.path;

              return (
                <button
                  key={file.path}
                  onClick={() => onSelect(file)}
                  onDoubleClick={() => onDoubleClick(file)}
                  className={`file-item w-full ${isSelected ? "selected" : ""}`}
                >
                  <Icon
                    className={`w-5 h-5 flex-shrink-0 ${
                      file.type === "directory"
                        ? "text-yellow-500"
                        : "text-pai-muted"
                    }`}
                  />
                  <span className="flex-1 text-left truncate">{file.name}</span>
                  {file.size !== undefined && (
                    <span className="text-xs text-pai-muted">
                      {formatFileSize(file.size)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="p-2 border-t border-pai-accent text-xs text-pai-muted">
        {files.length} items
      </div>
    </div>
  );
}

import React, { useState, useEffect } from "react";
import Head from "next/head";
import Sidebar from "@/components/Layout/Sidebar";
import FileBrowser from "@/components/Workspace/FileBrowser";
import FilePreview from "@/components/Workspace/FilePreview";
import { workspaceApi, FileItem, FileReadResponse } from "@/lib/api";
import {
  PlusIcon,
  ArrowUpTrayIcon,
  FolderPlusIcon,
} from "@heroicons/react/24/outline";

export default function WorkspacePage() {
  const [currentPath, setCurrentPath] = useState("/");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [fileData, setFileData] = useState<FileReadResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load files when path changes
  useEffect(() => {
    loadFiles();
  }, [currentPath]);

  const loadFiles = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const fileList = await workspaceApi.listFiles(currentPath);
      setFiles(fileList);
    } catch (err: any) {
      console.error("Failed to load files:", err);
      setError(err.message || "Failed to load files");
      setFiles([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNavigate = (path: string) => {
    setCurrentPath(path || "/");
    setSelectedFile(null);
    setFileData(null);
  };

  const handleSelectFile = async (file: FileItem) => {
    setSelectedFile(file);
    if (file.type === "file") {
      setIsPreviewLoading(true);
      try {
        const data = await workspaceApi.readFile(file.path);
        setFileData(data);
      } catch (err) {
        console.error("Failed to read file:", err);
        setFileData(null);
      } finally {
        setIsPreviewLoading(false);
      }
    }
  };

  const handleDoubleClick = (file: FileItem) => {
    if (file.type === "directory") {
      handleNavigate(file.path);
    }
  };

  const handleClosePreview = () => {
    setSelectedFile(null);
    setFileData(null);
  };

  const handleDeleteFile = async () => {
    if (!selectedFile) return;
    if (!confirm(`Are you sure you want to delete "${selectedFile.name}"?`))
      return;

    try {
      await workspaceApi.deleteFile(selectedFile.path);
      handleClosePreview();
      await loadFiles();
    } catch (err: any) {
      alert(`Failed to delete file: ${err.message}`);
    }
  };

  const handleCreateDirectory = async () => {
    const name = prompt("Enter directory name:");
    if (!name) return;

    try {
      const path = `${currentPath}/${name}`.replace(/\/+/g, "/");
      await workspaceApi.createDirectory(path);
      await loadFiles();
    } catch (err: any) {
      alert(`Failed to create directory: ${err.message}`);
    }
  };

  const handleUploadFile = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.onchange = async (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files?.length) return;

      for (const file of Array.from(files)) {
        try {
          // Send the current directory, not the full file path
          await workspaceApi.uploadFile(currentPath, file);
        } catch (err: any) {
          alert(`Failed to upload ${file.name}: ${err.message}`);
        }
      }
      await loadFiles();
    };
    input.click();
  };

  return (
    <>
      <Head>
        <title>Workspace - My PAI</title>
      </Head>
      <Sidebar>
        <div className="flex flex-col h-full">
          {/* Toolbar */}
          <div className="flex items-center justify-between p-4 border-b border-pai-accent bg-pai-card">
            <h1 className="text-xl font-bold">Workspace</h1>
            <div className="flex items-center gap-2">
              <button
                onClick={handleUploadFile}
                className="pai-button pai-button-secondary flex items-center gap-2"
              >
                <ArrowUpTrayIcon className="w-4 h-4" />
                Upload
              </button>
              <button
                onClick={handleCreateDirectory}
                className="pai-button pai-button-secondary flex items-center gap-2"
              >
                <FolderPlusIcon className="w-4 h-4" />
                New Folder
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 flex overflow-hidden">
            {/* File browser */}
            <div className="w-1/2 border-r border-pai-accent overflow-hidden">
              {isLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pai-highlight"></div>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-full text-pai-muted">
                  <p className="text-red-500">{error}</p>
                  <button
                    onClick={loadFiles}
                    className="mt-4 pai-button pai-button-secondary"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <FileBrowser
                  files={files}
                  currentPath={currentPath}
                  selectedFile={selectedFile?.path || null}
                  onNavigate={handleNavigate}
                  onSelect={handleSelectFile}
                  onDoubleClick={handleDoubleClick}
                />
              )}
            </div>

            {/* Preview panel */}
            <div className="w-1/2 overflow-hidden">
              <FilePreview
                file={selectedFile}
                fileData={fileData}
                isLoading={isPreviewLoading}
                onClose={handleClosePreview}
                onDelete={handleDeleteFile}
              />
            </div>
          </div>
        </div>
      </Sidebar>
    </>
  );
}

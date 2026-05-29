import React, { useState, useEffect, useMemo } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/cjs/styles/prism";
import {
  FileItem,
  FileReadResponse,
  PptxSlidesResponse,
  workspaceApi,
} from "@/lib/api";
import {
  XMarkIcon,
  ArrowDownTrayIcon,
  PencilIcon,
  TrashIcon,
  DocumentIcon,
  PhotoIcon,
  CodeBracketIcon,
  PresentationChartBarIcon,
  DocumentTextIcon,
} from "@heroicons/react/24/outline";

interface FilePreviewProps {
  file: FileItem | null;
  fileData: FileReadResponse | null;
  isLoading: boolean;
  onClose: () => void;
  onDelete?: () => void;
  onEdit?: () => void;
  onDownload?: () => void;
}

const getLanguage = (filename: string): string => {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  const langMap: Record<string, string> = {
    js: "javascript",
    jsx: "jsx",
    ts: "typescript",
    tsx: "tsx",
    py: "python",
    java: "java",
    c: "c",
    cpp: "cpp",
    h: "c",
    cs: "csharp",
    rb: "ruby",
    rs: "rust",
    go: "go",
    php: "php",
    swift: "swift",
    kt: "kotlin",
    scala: "scala",
    html: "html",
    css: "css",
    scss: "scss",
    less: "less",
    json: "json",
    xml: "xml",
    yaml: "yaml",
    yml: "yaml",
    md: "markdown",
    sql: "sql",
    sh: "bash",
    bash: "bash",
    zsh: "bash",
    ps1: "powershell",
    dockerfile: "docker",
    makefile: "makefile",
  };
  return langMap[ext] || "text";
};

const getFileType = (filename: string): string => {
  const ext = filename.split(".").pop()?.toLowerCase() || "";

  if (
    ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico"].includes(ext)
  ) {
    return "image";
  }

  const codeExtensions = [
    "txt",
    "md",
    "json",
    "xml",
    "yaml",
    "yml",
    "html",
    "css",
    "js",
    "jsx",
    "ts",
    "tsx",
    "py",
    "java",
    "c",
    "cpp",
    "h",
    "cs",
    "rb",
    "rs",
    "go",
    "php",
    "swift",
    "kt",
    "scala",
    "sql",
    "sh",
    "bash",
    "zsh",
    "ps1",
    "log",
    "ini",
    "conf",
    "cfg",
    "env",
    "gitignore",
    "dockerfile",
    "makefile",
  ];
  if (codeExtensions.includes(ext)) {
    return "code";
  }

  if (["ppt", "pptx", "odp"].includes(ext)) {
    return "powerpoint";
  }

  if (["doc", "docx", "odt", "rtf"].includes(ext)) {
    return "word";
  }

  if (ext === "pdf") {
    return "pdf";
  }

  if (["xls", "xlsx", "ods", "csv"].includes(ext)) {
    return "excel";
  }

  return "unknown";
};

const getMimeType = (filename: string): string => {
  const ext = filename.split(".").pop()?.toLowerCase() || "";
  const mimeMap: Record<string, string> = {
    png: "image/png",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    gif: "image/gif",
    webp: "image/webp",
    svg: "image/svg+xml",
    bmp: "image/bmp",
    ico: "image/x-icon",
    pdf: "application/pdf",
  };
  return mimeMap[ext] || "application/octet-stream";
};

const base64ToArrayBuffer = (base64: string): ArrayBuffer => {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
};

export default function FilePreview({
  file,
  fileData,
  isLoading,
  onClose,
  onDelete,
  onEdit,
  onDownload,
}: FilePreviewProps) {
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [docxHtml, setDocxHtml] = useState<string | null>(null);
  const [docxLoading, setDocxLoading] = useState(false);
  const [docxError, setDocxError] = useState<string | null>(null);
  const [pptxSlides, setPptxSlides] = useState<PptxSlidesResponse | null>(null);
  const [pptxLoading, setPptxLoading] = useState(false);
  const [pptxError, setPptxError] = useState<string | null>(null);
  const [currentSlide, setCurrentSlide] = useState(0);

  const fileType = file ? getFileType(file.name) : "unknown";
  const content = fileData?.content || "";
  const isBinary = fileData?.isBinary || false;

  useEffect(() => {
    if (file && fileType === "pdf" && isBinary && content) {
      try {
        const byteCharacters = atob(content);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        setPdfBlobUrl(url);

        return () => {
          URL.revokeObjectURL(url);
          setPdfBlobUrl(null);
        };
      } catch (e) {
        console.error("Failed to create PDF blob URL:", e);
      }
    } else {
      setPdfBlobUrl(null);
    }
  }, [file, fileType, isBinary, content]);

  useEffect(() => {
    const convertDocx = async () => {
      if (
        file &&
        fileType === "word" &&
        isBinary &&
        content &&
        file.name.endsWith(".docx")
      ) {
        setDocxLoading(true);
        setDocxError(null);
        try {
          const mammoth = (await import("mammoth")).default;
          const arrayBuffer = base64ToArrayBuffer(content);
          const result = await mammoth.convertToHtml({ arrayBuffer });
          setDocxHtml(result.value);
        } catch (e) {
          console.error("Failed to convert DOCX:", e);
          setDocxError("Failed to render document");
          setDocxHtml(null);
        } finally {
          setDocxLoading(false);
        }
      } else {
        setDocxHtml(null);
        setDocxError(null);
      }
    };
    convertDocx();
  }, [file, fileType, isBinary, content]);

  useEffect(() => {
    const fetchPptxSlides = async () => {
      if (
        file &&
        fileType === "powerpoint" &&
        (file.name.endsWith(".pptx") || file.name.endsWith(".ppt"))
      ) {
        setPptxLoading(true);
        setPptxError(null);
        setCurrentSlide(0);
        try {
          const slides = await workspaceApi.getPptxSlides(file.path);
          setPptxSlides(slides);
        } catch (e) {
          console.error("Failed to fetch PowerPoint slides:", e);
          setPptxError("Failed to load presentation");
          setPptxSlides(null);
        } finally {
          setPptxLoading(false);
        }
      } else {
        setPptxSlides(null);
        setPptxError(null);
      }
    };
    fetchPptxSlides();
  }, [file, fileType]);

  if (!file) {
    return (
      <div className="h-full flex items-center justify-center text-pai-muted">
        <p>Select a file to preview</p>
      </div>
    );
  }

  const handleDownload = () => {
    if (!fileData) return;

    let blob: Blob;
    if (isBinary) {
      const byteCharacters = atob(content);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      blob = new Blob([byteArray], { type: getMimeType(file.name) });
    } else {
      blob = new Blob([content], { type: "text/plain" });
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pai-highlight"></div>
        </div>
      );
    }

    if (!fileData) {
      return (
        <div className="flex flex-col items-center justify-center h-64 text-pai-muted">
          <DocumentIcon className="w-16 h-16 mb-4" />
          <p>Unable to load file content</p>
        </div>
      );
    }

    if (fileType === "image") {
      const imageUrl = isBinary
        ? `data:${getMimeType(file.name)};base64,${content}`
        : content;
      return (
        <div className="flex items-center justify-center p-4 bg-gray-900/50">
          <img
            src={imageUrl}
            alt={file.name}
            className="max-w-full max-h-[60vh] object-contain rounded shadow-lg"
          />
        </div>
      );
    }

    if (fileType === "code") {
      const language = getLanguage(file.name);
      const textContent = isBinary ? atob(content) : content;
      return (
        <div className="overflow-auto max-h-[60vh]">
          <SyntaxHighlighter
            language={language}
            style={vscDarkPlus}
            showLineNumbers
            wrapLines
            customStyle={{
              margin: 0,
              borderRadius: 0,
              background: "transparent",
              fontSize: "13px",
            }}
          >
            {textContent}
          </SyntaxHighlighter>
        </div>
      );
    }

    if (fileType === "pdf") {
      if (!pdfBlobUrl) {
        return (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pai-highlight"></div>
          </div>
        );
      }
      return (
        <div className="h-[60vh] w-full">
          <object
            data={pdfBlobUrl}
            type="application/pdf"
            className="w-full h-full"
          >
            <iframe
              src={pdfBlobUrl}
              className="w-full h-full border-0"
              title={file.name}
            />
          </object>
        </div>
      );
    }

    if (fileType === "powerpoint") {
      if (file.name.endsWith(".pptx") || file.name.endsWith(".ppt")) {
        if (pptxLoading) {
          return (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pai-highlight"></div>
            </div>
          );
        }
        if (pptxSlides && pptxSlides.slides.length > 0) {
          const slide = pptxSlides.slides[currentSlide];
          const isLegacyFormat = (pptxSlides as any).is_legacy_format === true;

          return (
            <div className="flex flex-col h-[60vh]">
              {isLegacyFormat && (
                <div className="px-4 py-2 bg-amber-500/20 border-b border-amber-500/30 text-amber-700 text-sm">
                  ⚠️ Legacy .ppt format - showing extracted text only. Slide
                  structure may not be preserved.
                </div>
              )}
              <div className="flex items-center justify-between px-4 py-2 bg-pai-accent/50 border-b border-pai-accent">
                <button
                  onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
                  disabled={currentSlide === 0}
                  className="px-3 py-1 rounded bg-pai-highlight text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  ← Prev
                </button>
                <span className="text-sm text-pai-text">
                  {isLegacyFormat
                    ? "Extracted Text"
                    : `Slide ${currentSlide + 1} of ${pptxSlides.slide_count}`}
                </span>
                <button
                  onClick={() =>
                    setCurrentSlide(
                      Math.min(pptxSlides.slides.length - 1, currentSlide + 1),
                    )
                  }
                  disabled={currentSlide >= pptxSlides.slides.length - 1}
                  className="px-3 py-1 rounded bg-pai-highlight text-white disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next →
                </button>
              </div>
              <div className="flex-1 overflow-auto p-6 bg-gradient-to-br from-orange-500/5 to-red-500/5">
                <div className="bg-white rounded-lg shadow-lg p-8 min-h-full">
                  {slide.texts.length > 0 ? (
                    <div className="space-y-4">
                      {slide.texts.map((text, idx) => (
                        <p
                          key={idx}
                          className={`text-gray-900 ${idx === 0 ? "text-2xl font-bold" : "text-base"}`}
                        >
                          {text}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 italic text-center">
                      No text content on this slide
                    </p>
                  )}
                  {slide.notes && (
                    <div className="mt-6 pt-4 border-t border-gray-200">
                      <p className="text-xs text-gray-500 font-semibold mb-1">
                        Speaker Notes:
                      </p>
                      <p className="text-sm text-gray-600">{slide.notes}</p>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-center py-2 bg-pai-accent/30">
                <button
                  onClick={handleDownload}
                  className="px-4 py-1 text-sm bg-pai-highlight text-white rounded hover:bg-pai-highlight/80 transition-colors flex items-center gap-2"
                >
                  <ArrowDownTrayIcon className="w-4 h-4" />
                  Download Original
                </button>
              </div>
            </div>
          );
        }
        if (pptxError) {
          return (
            <div className="flex flex-col items-center justify-center p-8 text-pai-muted">
              <PresentationChartBarIcon className="w-16 h-16 mb-4 text-red-400" />
              <p className="text-sm mb-4">{pptxError}</p>
              <button
                onClick={handleDownload}
                className="px-4 py-2 bg-pai-highlight text-white rounded-lg hover:bg-pai-highlight/80 transition-colors flex items-center gap-2"
              >
                <ArrowDownTrayIcon className="w-4 h-4" />
                Download Instead
              </button>
            </div>
          );
        }
      }
      return (
        <div className="flex flex-col items-center justify-center p-8 text-pai-muted">
          <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 p-8 rounded-2xl mb-6">
            <PresentationChartBarIcon className="w-24 h-24 text-orange-400" />
          </div>
          <h3 className="text-lg font-semibold text-pai-text mb-2">
            {file.name}
          </h3>
          <p className="text-sm mb-4">PowerPoint Presentation</p>
          <div className="flex gap-3">
            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-pai-highlight text-white rounded-lg hover:bg-pai-highlight/80 transition-colors flex items-center gap-2"
            >
              <ArrowDownTrayIcon className="w-4 h-4" />
              Download to View
            </button>
          </div>
        </div>
      );
    }

    if (fileType === "word") {
      if (file.name.endsWith(".docx")) {
        if (docxLoading) {
          return (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-pai-highlight"></div>
            </div>
          );
        }
        if (docxHtml) {
          return (
            <div className="overflow-auto max-h-[60vh] p-6 bg-white">
              <div
                className="prose prose-sm max-w-none text-gray-900"
                dangerouslySetInnerHTML={{ __html: docxHtml }}
              />
            </div>
          );
        }
        if (docxError) {
          return (
            <div className="flex flex-col items-center justify-center p-8 text-pai-muted">
              <DocumentTextIcon className="w-16 h-16 mb-4 text-red-400" />
              <p className="text-sm mb-4">{docxError}</p>
              <button
                onClick={handleDownload}
                className="px-4 py-2 bg-pai-highlight text-white rounded-lg hover:bg-pai-highlight/80 transition-colors flex items-center gap-2"
              >
                <ArrowDownTrayIcon className="w-4 h-4" />
                Download Instead
              </button>
            </div>
          );
        }
      }
      return (
        <div className="flex flex-col items-center justify-center p-8 text-pai-muted">
          <div className="bg-gradient-to-br from-blue-500/20 to-indigo-500/20 p-8 rounded-2xl mb-6">
            <DocumentTextIcon className="w-24 h-24 text-blue-400" />
          </div>
          <h3 className="text-lg font-semibold text-pai-text mb-2">
            {file.name}
          </h3>
          <p className="text-sm mb-4">Word Document (.doc format)</p>
          <div className="flex gap-3">
            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-pai-highlight text-white rounded-lg hover:bg-pai-highlight/80 transition-colors flex items-center gap-2"
            >
              <ArrowDownTrayIcon className="w-4 h-4" />
              Download to View
            </button>
          </div>
          <p className="text-xs mt-4 text-pai-muted/70">
            Legacy .doc format requires download
          </p>
        </div>
      );
    }

    if (fileType === "excel") {
      return (
        <div className="flex flex-col items-center justify-center p-8 text-pai-muted">
          <div className="bg-gradient-to-br from-green-500/20 to-emerald-500/20 p-8 rounded-2xl mb-6">
            <DocumentIcon className="w-24 h-24 text-green-400" />
          </div>
          <h3 className="text-lg font-semibold text-pai-text mb-2">
            {file.name}
          </h3>
          <p className="text-sm mb-4">Excel Spreadsheet</p>
          <div className="flex gap-3">
            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-pai-highlight text-white rounded-lg hover:bg-pai-highlight/80 transition-colors flex items-center gap-2"
            >
              <ArrowDownTrayIcon className="w-4 h-4" />
              Download to View
            </button>
          </div>
          <p className="text-xs mt-4 text-pai-muted/70">
            Download and open with Microsoft Excel or Google Sheets
          </p>
        </div>
      );
    }

    // Unknown file type
    return (
      <div className="flex flex-col items-center justify-center p-8 text-pai-muted">
        <div className="bg-pai-accent/30 p-8 rounded-2xl mb-6">
          <DocumentIcon className="w-24 h-24" />
        </div>
        <h3 className="text-lg font-semibold text-pai-text mb-2">
          {file.name}
        </h3>
        <p className="text-sm mb-4">Preview not available for this file type</p>
        <button
          onClick={handleDownload}
          className="px-4 py-2 bg-pai-highlight text-white rounded-lg hover:bg-pai-highlight/80 transition-colors flex items-center gap-2"
        >
          <ArrowDownTrayIcon className="w-4 h-4" />
          Download File
        </button>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-pai-card">
      <div className="flex items-center justify-between p-3 border-b border-pai-accent">
        <h3 className="font-medium truncate" title={file.name}>
          {file.name}
        </h3>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={handleDownload}
            className="p-1 text-pai-muted hover:text-pai-text transition-colors"
            title="Download"
          >
            <ArrowDownTrayIcon className="w-5 h-5" />
          </button>
          {onEdit && fileType === "code" && (
            <button
              onClick={onEdit}
              className="p-1 text-pai-muted hover:text-pai-text transition-colors"
              title="Edit"
            >
              <PencilIcon className="w-5 h-5" />
            </button>
          )}
          {onDelete && (
            <button
              onClick={onDelete}
              className="p-1 text-pai-muted hover:text-pai-highlight transition-colors"
              title="Delete"
            >
              <TrashIcon className="w-5 h-5" />
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 text-pai-muted hover:text-pai-text transition-colors"
            title="Close"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">{renderContent()}</div>

      <div className="p-2 border-t border-pai-accent text-xs text-pai-muted flex justify-between">
        <span className="truncate" title={file.path}>
          {file.path}
        </span>
        <span className="flex-shrink-0 ml-2">
          {file.size !== undefined && `${(file.size / 1024).toFixed(1)} KB`}
        </span>
      </div>
    </div>
  );
}

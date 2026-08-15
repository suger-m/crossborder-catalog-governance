// Adapted from ../_reference/eigent/src/components/ChatBox/BottomBox/InputBox.tsx.
// Controlled version: attachments are metadata selected through coworkDesktop.

import { ArrowRight, FileText, Image, Maximize2, Paperclip, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { ASK_PLACEHOLDER } from '@/lib/brand';
import type { CoworkInputAttachment } from '@/types';

export type FileAttachment = CoworkInputAttachment;

export interface InputBoxProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  files: FileAttachment[];
  onFilesChange: (files: FileAttachment[]) => void;
  onAddFile: () => void;
  onExpand?: () => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  hideExpandButton?: boolean;
  canSend?: boolean;
  sendTitle?: string;
}

function FileIcon({ fileName }: { fileName: string }) {
  const ext = fileName.split('.').pop()?.toLowerCase() || '';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(ext)) {
    return <Image size={14} />;
  }
  return <FileText size={14} />;
}

export function InputBox({
  value,
  onChange,
  onSend,
  files,
  onFilesChange,
  onAddFile,
  onExpand,
  placeholder = ASK_PLACEHOLDER,
  disabled = false,
  className = '',
  hideExpandButton = false,
  canSend,
  sendTitle = '发送',
}: InputBoxProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const hasContent = value.trim().length > 0 || files.length > 0;
  const sendEnabled = !disabled && (canSend ?? hasContent);

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`;
  }, [value]);

  const removeFile = (filePath: string) => {
    onFilesChange(files.filter((file) => file.filePath !== filePath));
  };

  const send = () => {
    if (!sendEnabled) return;
    onSend();
  };

  return (
    <div className={`chat-inputbox ${isFocused || hasContent ? 'active' : ''} ${className}`}>
      {files.length > 0 ? (
        <div className="chat-input-attachments">
          {files.map((file) => (
            <span className="chat-input-file" key={file.filePath} title={file.filePath}>
              <FileIcon fileName={file.fileName} />
              <strong>{file.fileName}</strong>
              <button
                disabled={disabled}
                onClick={() => removeFile(file.filePath)}
                title="移除文件"
                type="button"
              >
                <X size={13} />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      <textarea
        className="chat-input-textarea"
        data-chat-input
        disabled={disabled}
        onBlur={() => setIsFocused(false)}
        onChange={(event) => onChange(event.target.value)}
        onFocus={() => setIsFocused(true)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            send();
          }
        }}
        placeholder={placeholder}
        ref={textareaRef}
        rows={1}
        value={value}
      />

      <div className="chat-input-actions">
        <button
          className="chat-input-tool"
          disabled={disabled}
          onClick={onAddFile}
          title="添加数据文件"
          type="button"
        >
          <Paperclip size={16} />
        </button>
        {!hideExpandButton ? (
          <button
            className="chat-input-tool"
            data-expanded-input-trigger
            disabled={disabled}
            onClick={onExpand}
            title="展开输入框"
            type="button"
          >
            <Maximize2 size={16} />
          </button>
        ) : null}
        <button
          className="chat-input-send"
          data-active={String(sendEnabled)}
          disabled={!sendEnabled}
          onClick={send}
          title={sendTitle}
          type="button"
        >
          <ArrowRight size={17} />
        </button>
      </div>
    </div>
  );
}

/**
 * Cross-border native task projection consumed by the migrated reference
 * workspace components. It is a typed view of backend state, not a second
 * execution store and not a legacy cowork adapter.
 */
export interface Task {
  id: string;
  summaryTask: string;
  messages: Message[];
  taskInfo: TaskInfo[];
  taskAssigning: Agent[];
  progressValue: number;
  isTakeControl?: boolean;
  fileList: FileInfo[];
  activeWorkspace?: string;
  selectedFile?: FileInfo;
}

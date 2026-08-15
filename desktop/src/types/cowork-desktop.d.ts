interface CoworkDataFile {
  path: string;
  name: string;
  extension: string;
}

interface Window {
  coworkDesktop?: {
    selectDataFile(options: { title: string; multiple: boolean; allowedExtensions: string[] }): Promise<{ canceled: boolean; files: CoworkDataFile[] }>;
  };
}

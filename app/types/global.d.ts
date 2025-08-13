declare global {
  interface Window {
    __TAURI__?: {
      invoke: (cmd: string, args?: any) => Promise<any>;
      listen: (
        event: string,
        handler: (event: any) => void,
      ) => Promise<() => void>;
    };
  }
}

export {};

/// <reference types="vite/client" />
declare const __PLATFORM__: 'telegram' | 'max'

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

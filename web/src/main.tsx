import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5000, retry: 3 },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'rgba(255, 255, 255, 0.85)',
            backdropFilter: 'blur(12px)',
            color: '#1E293B',
            borderRadius: '12px',
            fontSize: '14px',
            border: '1px solid rgba(255, 255, 255, 0.6)',
            boxShadow: '0 4px 24px rgba(0, 0, 0, 0.08)',
          },
        }}
      />
    </QueryClientProvider>
  </React.StrictMode>
)

import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { AppProvider } from './app/AppContext';
import App from './app/App.tsx';
import './styles/index.css';

createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <AppProvider>
      <App />
    </AppProvider>
  </BrowserRouter>,
);

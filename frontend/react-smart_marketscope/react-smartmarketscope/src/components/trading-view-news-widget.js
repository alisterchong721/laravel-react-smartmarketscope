// TradingViewNewsWidget.jsx - UPDATED
import React, { useEffect, useRef, memo } from 'react';

function TradingViewNewsWidget({ onLoad }) {
  const container = useRef();

  useEffect(() => {
    // Clear container
    container.current.innerHTML = '';

    // Create iframe instead of script
    const iframe = document.createElement('iframe');
    iframe.src =
      'https://www.tradingview.com/embed-widget/timeline/?locale=en#%7B%22colorTheme%22%3A%22light%22%2C%22displayMode%22%3A%22regular%22%2C%22width%22%3A%22100%25%22%2C%22height%22%3A%22500%22%2C%22isTransparent%22%3Afalse%2C%22feedMode%22%3A%22all_symbols%22%7D';
    iframe.style.width = '100%';
    iframe.style.height = '500px';
    iframe.style.border = 'none';
    iframe.allow = 'clipboard-write';
    iframe.referrerPolicy = 'no-referrer-when-downgrade';
    iframe.sandbox =
      'allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox';

    iframe.onload = () => {
      if (onLoad) onLoad();
    };

    iframe.onerror = () => {
      if (onLoad) onLoad();
      console.error('Failed to load TradingView widget');
    };

    container.current.appendChild(iframe);

    return () => {
      if (iframe.parentNode) {
        iframe.parentNode.removeChild(iframe);
      }
    };
  }, [onLoad]);

  return <div ref={container} style={{ width: '100%', height: '500px' }} />;
}

export default memo(TradingViewNewsWidget);

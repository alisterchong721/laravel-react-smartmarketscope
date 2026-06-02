import React, { useEffect, useRef, memo } from 'react';

function TradingViewForexHeatmap({ onLoad }) {
  const container = useRef();

  useEffect(() => {
    // Clear container
    container.current.innerHTML = '';

    // Create iframe
    const iframe = document.createElement('iframe');
    iframe.src =
      'https://www.tradingview.com/embed-widget/forex-heat-map/?locale=en#%7B%22colorTheme%22%3A%22light%22%2C%22isTransparent%22%3Afalse%2C%22width%22%3A%22100%25%22%2C%22height%22%3A%22500%22%2C%22currencies%22%3A%5B%22EUR%22%2C%22USD%22%2C%22JPY%22%2C%22GBP%22%2C%22AUD%22%2C%22CAD%22%5D%7D';
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
      console.error('Failed to load TradingView heatmap');
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

export default memo(TradingViewForexHeatmap);

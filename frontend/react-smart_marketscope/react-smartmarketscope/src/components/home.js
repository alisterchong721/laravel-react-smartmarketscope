import React, { useState } from 'react';
import Sidebar from './sidebar';
import { Row, Col, Card, Table, Spin, Typography } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import TradingViewNewsWidget from './trading-view-news-widget';
import TradingViewForexHeatmap from './trading-view-forex-heatmap';

const Home = () => {
  const [newsWidgetLoading, setNewsWidgetLoading] = useState(true);
  const [heatmapLoading, setHeatmapLoading] = useState(true);

  return (
    <Sidebar>
      <Row gutter={[20, 20]}>
        {/* Left Column - News Widget */}
        <Col xs={24} sm={24} lg={12}>
          <Card title="Financial News Timeline" style={{ width: '100%' }}>
            <div
              style={{
                width: '100%',
                height: '500px',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {newsWidgetLoading && (
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(255, 255, 255, 0.8)',
                    zIndex: 10,
                  }}
                >
                  <Spin
                    indicator={
                      <LoadingOutlined style={{ fontSize: 24 }} spin />
                    }
                    size="large"
                  />
                  <Typography.Text
                    type="secondary"
                    style={{ marginTop: '10px' }}
                  >
                    Loading news feed...
                  </Typography.Text>
                </div>
              )}
              <TradingViewNewsWidget
                onLoad={() => setNewsWidgetLoading(false)}
              />
            </div>
          </Card>
        </Col>

        {/* Right Column - Heatmap */}
        <Col xs={24} sm={24} lg={12}>
          <Card title="Currencies Heatmap" style={{ width: '100%' }}>
            <div
              style={{
                width: '100%',
                height: '500px',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {heatmapLoading && (
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(255, 255, 255, 0.8)',
                    zIndex: 10,
                  }}
                >
                  <Spin
                    indicator={
                      <LoadingOutlined style={{ fontSize: 24 }} spin />
                    }
                    size="large"
                  />
                  <Typography.Text
                    type="secondary"
                    style={{ marginTop: '10px' }}
                  >
                    Loading heatmap...
                  </Typography.Text>
                </div>
              )}
              <TradingViewForexHeatmap
                onLoad={() => setHeatmapLoading(false)}
              />
            </div>
          </Card>
        </Col>
      </Row>
    </Sidebar>
  );
};

export default Home;

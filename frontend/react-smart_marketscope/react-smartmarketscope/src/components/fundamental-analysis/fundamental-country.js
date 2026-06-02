import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';
import Sidebar from '../sidebar';
import { Button, Col, Row, Table, Typography, Grid, Spin, Alert, Tag, Space } from 'antd';

// MUI Icon
import RefreshIcon from '@mui/icons-material/Refresh';
import { fetchFundamentalCountry } from '../../actions/fundamentalDataActions';
import './fundamental-analysis.css';
const { Title } = Typography;

const getImpactColor = (impact) => {
  if (impact === 'Bullish') return 'green';
  if (impact === 'Bearish') return 'red';
  return 'default';
};

const columns = [
  {
    title: 'Economic Data',
    dataIndex: 'economicData',
    key: 'economicData',
  },
  {
    title: 'Actual',
    dataIndex: 'actual',
    key: 'actual',
    render: (text, record) => {
      const actualColor = record.actualColor || record.actual_color || getImpactColor(record.impact);

      return (
        <span className={`fundamental-calendar-actual fundamental-calendar-actual-${actualColor}`}>
          {text}
        </span>
      );
    },
  },
  {
    title: 'Forecast',
    dataIndex: 'forecast',
    key: 'forecast',
  },
  {
    title: 'Previous',
    dataIndex: 'previous',
    key: 'previous',
  },
  {
    title: 'Date',
    dataIndex: 'date',
    key: 'date',
  },
  {
    title: 'Impact',
    dataIndex: 'impact',
    key: 'impact',
    render: (text) => {
      let color = 'default';
      if (text === 'Bullish') color = 'green';
      if (text === 'Bearish') color = 'red';
      return <span style={{ color }}>{text}</span>;
    },
  },
  {
    title: 'Source',
    dataIndex: 'source',
    key: 'source',
    render: (text, record) => {
      if (record.isLiveSource) {
        return (
          <Space size={4} wrap>
            <Tag color="blue">Forex Factory</Tag>
            {record.actualSource && <Tag color="cyan">Actual: {record.actualSource}</Tag>}
          </Space>
        );
      }

      if (record.isPendingSource) {
        return <Tag color="gold">Awaiting Forex Factory</Tag>;
      }

      return <Tag color="default">{text}</Tag>;
    },
  },
];

const FundamentalCountry = () => {
  const { useBreakpoint } = Grid;
  const screens = useBreakpoint();
  const dispatch = useDispatch();
  const { countryType = 'us' } = useParams(); // Get country type from URL

  // Get data from Redux store
  const { data, loading, error, lastUpdated } = useSelector(
    (state) => state.fundamental
  );

  // Fetch data on component mount
  useEffect(() => {
    dispatch(fetchFundamentalCountry(countryType));
  }, [dispatch, countryType]);

  const handleRefresh = () => {
    dispatch(fetchFundamentalCountry(countryType));
  };

  // Get country name based on type
  const getCountryName = (type) => {
    const countries = {
      us: 'United States',
      uk: 'United Kingdom',
      eurozone: 'European Union',
      japan: 'Japan',
      australia: 'Australia',
      canada: 'Canada',
    };
    const countryCode = (type || '').toLowerCase();
    return countries[countryCode] || countryCode.toUpperCase();
  };

  if (error) {
    return (
      <Sidebar>
        <Alert
          message="Error"
          description={error}
          type="error"
          showIcon
          style={{ margin: '20px 0' }}
        />
        <Button onClick={handleRefresh} type="primary">
          Retry
        </Button>
      </Sidebar>
    );
  }

  return (
    <>
      <Sidebar>
        <Row justify="space-between" gutter={[16, 16]} align="middle">
          <Col xs={24} sm={12} lg={14}>
            <Title level={2}>
              {getCountryName(countryType)} Economic Data
              {lastUpdated && (
                <span
                  style={{
                    fontSize: '14px',
                    color: '#666',
                    marginLeft: '10px',
                  }}
                >
                  (Updated: {new Date(lastUpdated).toLocaleTimeString()})
                </span>
              )}
            </Title>
          </Col>

          <Col xs={24} sm={12} lg={10}>
            <Row justify="end">
              <Col xs={24} sm={12} lg={6}>
                <Button
                  type="primary"
                  icon={<RefreshIcon />}
                  block
                  onClick={handleRefresh}
                  loading={loading}
                  style={{
                    fontSize: screens.xs ? '10px' : '12px',
                    padding: '6px 8px',
                  }}
                >
                  <span
                    style={{
                      whiteSpace: 'nowrap',
                      textOverflow: 'ellipsis',
                      overflow: 'hidden',
                    }}
                  >
                    Refresh
                  </span>
                </Button>
              </Col>
            </Row>
          </Col>
        </Row>

        <Row>
          <Col xs={24} sm={24}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '50px' }}>
                <Spin size="large" />
                <p>Loading economic data...</p>
              </div>
            ) : (
              <Table
                dataSource={data}
                columns={columns}
                pagination={false}
                scroll={{ x: true }}
                style={{
                  ...(screens.xs && {
                    marginTop: '10px',
                  }),
                }}
                rowKey="key"
              />
            )}
          </Col>
        </Row>
      </Sidebar>
    </>
  );
};

export default FundamentalCountry;

import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';
import Sidebar from '../sidebar';
import {
  Button,
  Col,
  Row,
  Typography,
  Grid,
  Spin,
  Alert,
  Card,
  Statistic,
  Tag,
  Space,
  Empty,
} from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
} from '@ant-design/icons';
import RefreshIcon from '@mui/icons-material/Refresh';
import { fetchCurrencyPair } from '../../actions/fundamentalPairActions';

const { Title, Text } = Typography;

const CurrencyPair = () => {
  const { useBreakpoint } = Grid;
  const screens = useBreakpoint();
  const dispatch = useDispatch();
  const { pair = 'EURUSD' } = useParams();

  const { pairData, pairLoading, pairError } = useSelector(
    (state) => state.fundamentalPair || {}
  );

  useEffect(() => {
    if (pair) {
      dispatch(fetchCurrencyPair(pair.toUpperCase()));
    }
  }, [dispatch, pair]);

  const handleRefresh = () => {
    dispatch(fetchCurrencyPair(pair.toUpperCase()));
  };

  const formatPairName = (pair) => {
    const formattedUpperCasePair = pair.toUpperCase();
    if (formattedUpperCasePair?.length === 6) {
      return `${formattedUpperCasePair.slice(
        0,
        3
      )}/${formattedUpperCasePair.slice(3)}`;
    }
    return formattedUpperCasePair;
  };

  // --- LOGIC FIX START ---
  // We derive the pair score and impact locally to ensure the math is always Base - Quote
  const baseScore = pairData?.base_score || 0;
  const quoteScore = pairData?.quote_score || 0;
  const calculatedPairScore = baseScore - quoteScore;

  const getImpactConfig = (score) => {
    if (score > 0)
      return { color: '#52c41a', icon: <ArrowUpOutlined />, text: 'BULLISH' };
    if (score < 0)
      return { color: '#ff4d4f', icon: <ArrowDownOutlined />, text: 'BEARISH' };
    return { color: '#d9d9d9', icon: <MinusOutlined />, text: 'NEUTRAL' };
  };

  const impact = getImpactConfig(calculatedPairScore);
  // --- LOGIC FIX END ---

  if (pairError) {
    return (
      <Sidebar>
        <Alert
          message="Error"
          description={pairError}
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
    <Sidebar>
      <Row justify="space-between" gutter={[16, 16]} align="middle">
        <Col xs={24} sm={12} lg={14}>
          <Title level={2}>
            Currency Pair Analysis: {formatPairName(pair)}
            <Tag
              color={impact.color}
              icon={impact.icon}
              style={{ marginLeft: 10, fontSize: '16px', padding: '4px 12px' }}
            >
              {impact.text}
            </Tag>
          </Title>
        </Col>

        <Col xs={24} sm={12} lg={10}>
          <Row justify="end" gutter={[8, 8]}>
            <Col>
              <Button
                type="primary"
                icon={<RefreshIcon />}
                onClick={handleRefresh}
                loading={pairLoading}
              >
                Refresh
              </Button>
            </Col>
          </Row>
        </Col>
      </Row>

      {pairLoading ? (
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Spin size="large" />
          <p>Loading data...</p>
        </div>
      ) : pairData ? (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title="Pair Strength Differential"
                  value={calculatedPairScore}
                  valueStyle={{ color: impact.color }}
                  prefix={impact.icon}
                />
                <Text type="secondary">
                  Base ({baseScore}) - Quote ({quoteScore}) ={' '}
                  {calculatedPairScore}
                </Text>
              </Card>
            </Col>

            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title="Base Currency"
                  value={pairData.base_currency}
                  suffix={`(${pairData.base_country})`}
                />
                <Text
                  strong
                  style={{ color: baseScore >= 0 ? '#52c41a' : '#ff4d4f' }}
                >
                  Score: {baseScore > 0 ? `+${baseScore}` : baseScore}
                </Text>
              </Card>
            </Col>

            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title="Quote Currency"
                  value={pairData.quote_currency}
                  suffix={`(${pairData.quote_country})`}
                />
                <Text
                  strong
                  style={{ color: quoteScore >= 0 ? '#52c41a' : '#ff4d4f' }}
                >
                  Score: {quoteScore > 0 ? `+${quoteScore}` : quoteScore}
                </Text>
              </Card>
            </Col>
          </Row>

          <Card title="Score Interpretation" style={{ marginBottom: 24 }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Text>
                <Text strong>
                  Positive Score ({calculatedPairScore > 0 ? '✓' : '✗'})
                </Text>
                :{pairData.base_currency} is mathematically stronger than{' '}
                {pairData.quote_currency}. Expect <b>{formatPairName(pair)}</b>{' '}
                to rise.
              </Text>
              <Text>
                <Text strong>
                  Negative Score ({calculatedPairScore < 0 ? '✓' : '✗'})
                </Text>
                :{pairData.quote_currency} is mathematically stronger than{' '}
                {pairData.base_currency}. Expect <b>{formatPairName(pair)}</b>{' '}
                to fall.
              </Text>
              <Text>
                <Text strong>Calculation</Text>: {baseScore} (Base) -{' '}
                {quoteScore} (Quote) = {calculatedPairScore}
              </Text>
            </Space>
          </Card>
        </>
      ) : (
        <Empty description="No data available" />
      )}
    </Sidebar>
  );
};

export default CurrencyPair;

import React, { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  Alert,
  Button,
  Col,
  Drawer,
  Empty,
  Grid,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  EyeOutlined,
  MenuFoldOutlined,
  ReloadOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import Sidebar from './sidebar';
import {
  fetchOverviewDashboardFiltersRequest,
  fetchOverviewDashboardRequest,
} from '../actions/overviewDashboardActions';
import './overview.css';

const { Title, Text } = Typography;

const preferredPairOrder = ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDJPY'];

const formatPair = (value) => {
  const normalized = (value || '').toUpperCase();

  return normalized.length === 6
    ? `${normalized.slice(0, 3)}/${normalized.slice(3)}`
    : normalized;
};

const formatNumber = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-';
  }

  return new Intl.NumberFormat('en-US').format(Number(value));
};

const formatScore = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-';
  }

  return Number(value) > 0 ? `+${Number(value)}` : Number(value);
};

const titleCase = (value) =>
  (value || 'unavailable')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());

const normalizeBias = (bias) =>
  (bias || '')
    .toString()
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');

const getBiasDirection = (bias) => {
  const normalizedBias = normalizeBias(bias);

  if (normalizedBias.includes('bearish')) {
    return 'bearish';
  }

  if (normalizedBias.includes('bullish')) {
    return 'bullish';
  }

  return normalizedBias === 'neutral' ? 'neutral' : null;
};

const formatBiasLabel = (bias) => {
  const normalizedBias = normalizeBias(bias);
  const labels = {
    strong_bullish: 'Strong Bullish',
    strong_bearish: 'Strong Bearish',
    very_bullish: 'Strong Bullish',
    very_bearish: 'Strong Bearish',
  };

  return labels[normalizedBias] || titleCase(normalizedBias || bias);
};

const getScoreColor = (score) => {
  if (score === null || score === undefined) {
    return '#8c8c8c';
  }

  if (Number(score) > 0) {
    return '#16a34a';
  }

  if (Number(score) < 0) {
    return '#dc2626';
  }

  return '#8c8c8c';
};

const getBiasColor = (bias) => {
  const direction = getBiasDirection(bias);

  if (direction === 'bullish') {
    return 'green';
  }

  if (direction === 'bearish') {
    return 'red';
  }

  return 'gold';
};

const getBiasTagStyle = (bias) => {
  const direction = getBiasDirection(bias);

  if (direction === 'bullish') {
    return {
      color: '#15803d',
      backgroundColor: '#f0fdf4',
      borderColor: '#bbf7d0',
    };
  }

  if (direction === 'bearish') {
    return {
      color: '#dc2626',
      backgroundColor: '#fef2f2',
      borderColor: '#fecaca',
    };
  }

  return undefined;
};

const getBiasTagClassName = (bias) => {
  const direction = getBiasDirection(bias);

  return direction ? `overview-bias-tag overview-bias-tag--${direction}` : undefined;
};

const isBullishBias = (bias) => getBiasDirection(bias) === 'bullish';
const isBearishBias = (bias) => getBiasDirection(bias) === 'bearish';

const isNeutralBias = (bias) => getBiasDirection(bias) === 'neutral';

const sortPairs = (items) =>
  [...items].sort((left, right) => {
    const leftIndex = preferredPairOrder.indexOf(left.asset_symbol);
    const rightIndex = preferredPairOrder.indexOf(right.asset_symbol);

    if (leftIndex === -1 && rightIndex === -1) {
      return left.asset_symbol.localeCompare(right.asset_symbol);
    }

    if (leftIndex === -1) {
      return 1;
    }

    if (rightIndex === -1) {
      return -1;
    }

    return leftIndex - rightIndex;
  });

const scoreColumn = (title, key, selector) => ({
  title,
  key,
  sorter: (left, right) => Number(selector(left) || 0) - Number(selector(right) || 0),
  render: (_, record) => {
    const value = selector(record);

    return (
      <Text strong style={{ color: getScoreColor(value) }}>
        {formatScore(value)}
      </Text>
    );
  },
});

const componentRows = (record) => [
  {
    label: 'Fundamental',
    component: record?.fundamental,
    detail: record?.fundamental?.available
      ? `Raw pair score ${formatScore(record.fundamental.raw_pair_score)}`
      : record?.fundamental?.error,
  },
  {
    label: 'COT',
    component: record?.sentiment?.components?.cot,
    detail: record?.sentiment?.components?.cot?.available
      ? `Net position ${formatNumber(record.sentiment.components.cot.net_position)}`
      : record?.sentiment?.components?.cot?.error,
  },
  {
    label: 'Retail',
    component: record?.sentiment?.components?.retail,
    detail: record?.sentiment?.components?.retail?.available
      ? `Buy ${record.sentiment.components.retail.average_buy_percentage}% / Sell ${record.sentiment.components.retail.average_sell_percentage}%`
      : record?.sentiment?.components?.retail?.error,
  },
  {
    label: 'News',
    component: record?.sentiment?.components?.news,
    detail: record?.sentiment?.components?.news?.available
      ? `${record.sentiment.components.news.total_articles} articles`
      : record?.sentiment?.components?.news?.error,
  },
  {
    label: 'Seasonality',
    component: record?.seasonality,
    detail: record?.seasonality?.available
      ? `${record.seasonality.month_name} average ${formatScore(record.seasonality.average_return)}%`
      : record?.seasonality?.error,
  },
];

const Overview = () => {
  const dispatch = useDispatch();
  const { useBreakpoint } = Grid;
  const screens = useBreakpoint();
  const [isSimpleView, setIsSimpleView] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedPair, setSelectedPair] = useState(null);

  const {
    query,
    filtersLoading,
    filtersError,
    overviewData,
    loading,
    error,
    lastUpdated,
  } = useSelector((state) => state.overviewDashboard || {});

  useEffect(() => {
    dispatch(fetchOverviewDashboardFiltersRequest());
    dispatch(fetchOverviewDashboardRequest());
  }, [dispatch]);

  const overviewRows = useMemo(
    () =>
      sortPairs(overviewData?.items || []).map((item) => ({
        ...item,
        key: item.asset_symbol,
      })),
    [overviewData]
  );

  const selectedRow = useMemo(
    () =>
      selectedPair
        ? overviewRows.find((item) => item.asset_symbol === selectedPair)
        : overviewRows[0],
    [overviewRows, selectedPair]
  );

  const summary = useMemo(() => {
    const ranked = [...overviewRows].sort(
      (left, right) => Number(right?.overall?.score || 0) - Number(left?.overall?.score || 0)
    );

    return {
      totalAssets: overviewData?.summary?.total_assets || overviewRows.length,
      bullishCount: overviewRows.filter((item) => isBullishBias(item?.overall?.bias))
        .length,
      neutralCount: overviewRows.filter((item) => isNeutralBias(item?.overall?.bias))
        .length,
      bearishCount: overviewRows.filter((item) => isBearishBias(item?.overall?.bias))
        .length,
      strongest: ranked[0] || null,
    };
  }, [overviewData?.summary?.total_assets, overviewRows]);

  const openQuickAccess = (assetSymbol) => {
    setSelectedPair(assetSymbol);
    setDrawerOpen(true);
  };

  const handleRefresh = () => {
    dispatch(
      fetchOverviewDashboardRequest({
        ...query,
        refresh: true,
      })
    );
  };

  const navigateToPair = (path) => {
    window.open(path, '_blank', 'noopener,noreferrer');
  };

  const baseColumns = [
    {
      title: 'Asset',
      dataIndex: 'asset_symbol',
      key: 'asset_symbol',
      fixed: screens.lg ? 'left' : false,
      render: (value, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{formatPair(value)}</Text>
          <Text type="secondary">{record.display_name}</Text>
        </Space>
      ),
    },
    scoreColumn('Fundamental Score', 'fundamental_score', (record) => record?.fundamental?.score),
    scoreColumn('Sentimental Score', 'sentiment_score', (record) => record?.sentiment?.score),
    scoreColumn('Seasonality Score', 'seasonality_score', (record) => record?.seasonality?.score),
    scoreColumn('Total Score', 'total_score', (record) => record?.overall?.score),
    {
      title: 'Bias',
      key: 'bias',
      render: (_, record) => (
        <Tag
          color={getBiasColor(record?.overall?.bias)}
          className={getBiasTagClassName(record?.overall?.bias)}
          style={getBiasTagStyle(record?.overall?.bias)}
        >
          {formatBiasLabel(record?.overall?.bias)}
        </Tag>
      ),
    },
    {
      title: 'Quick Access',
      key: 'quick_access',
      fixed: screens.lg ? 'right' : false,
      render: (_, record) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => openQuickAccess(record.asset_symbol)}
        >
          Open
        </Button>
      ),
    },
  ];

  const advancedColumns = [
    baseColumns[0],
    baseColumns[1],
    scoreColumn('COT', 'cot_score', (record) => record?.sentiment?.components?.cot?.score),
    scoreColumn('Retail', 'retail_score', (record) => record?.sentiment?.components?.retail?.score),
    scoreColumn('News', 'news_score', (record) => record?.sentiment?.components?.news?.score),
    baseColumns[3],
    baseColumns[2],
    baseColumns[4],
    baseColumns[5],
    baseColumns[6],
  ];

  return (
    <Sidebar>
      <div className="overview-page">
        <Row gutter={[16, 16]} justify="space-between" align="middle">
          <Col xs={24} lg={12}>
            <Title level={2} style={{ margin: 0 }}>
              Overview Setup - {isSimpleView ? 'Simple' : 'Advanced'}
            </Title>
          </Col>

          <Col xs={24} lg={12}>
            <div className="overview-toolbar">
              <Button
                icon={<MenuFoldOutlined />}
                onClick={() => openQuickAccess(selectedRow?.asset_symbol)}
                disabled={!overviewRows.length}
              >
                Quick Access
              </Button>
              <Button
                type="primary"
                icon={<SwapOutlined />}
                onClick={() => setIsSimpleView((previous) => !previous)}
              >
                Switch to {isSimpleView ? 'Advanced' : 'Simple'} View
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={loading || filtersLoading}
              >
                Refresh
              </Button>
            </div>
          </Col>
        </Row>

        {filtersError || error ? (
          <Alert
            message="Overview data error"
            description={filtersError || error}
            type="error"
            showIcon
          />
        ) : null}

        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <div className="overview-summary-card">
              <Statistic title="Tracked Assets" value={summary.totalAssets} />
              <Text type="secondary">Combined backend scoring</Text>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div className="overview-summary-card">
              <Statistic
                title="Bullish / Neutral / Bearish"
                value={`${summary.bullishCount} / ${summary.neutralCount} / ${summary.bearishCount}`}
              />
              <Text type="secondary">Uses the -100 to +100 bias scale</Text>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div className="overview-summary-card">
              <Statistic
                title="Strongest Bias"
                value={summary.strongest ? formatPair(summary.strongest.asset_symbol) : '-'}
              />
              <Text type="secondary">
                Total score: {formatScore(summary.strongest?.overall?.score)}
              </Text>
            </div>
          </Col>
        </Row>

        <Table
          rowKey="asset_symbol"
          columns={isSimpleView ? baseColumns : advancedColumns}
          dataSource={overviewRows}
          loading={loading || filtersLoading}
          locale={{
            emptyText: <Empty description="No overview data available yet" />,
          }}
          pagination={false}
          scroll={{ x: isSimpleView ? 1040 : 1320 }}
          onRow={(record) => ({
            onDoubleClick: () => openQuickAccess(record.asset_symbol),
          })}
        />

        <Drawer
          title={
            selectedRow
              ? `${formatPair(selectedRow.asset_symbol)} Quick Access`
              : 'Quick Access'
          }
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={screens.xs ? '86%' : 400}
        >
          {selectedRow ? (
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">Total bias</Text>
                <div className="overview-drawer-title-row">
                  <Title level={3} style={{ margin: 0 }}>
                    {formatPair(selectedRow.asset_symbol)}
                  </Title>
                  <Tag
                    color={getBiasColor(selectedRow?.overall?.bias)}
                    className={getBiasTagClassName(selectedRow?.overall?.bias)}
                    style={getBiasTagStyle(selectedRow?.overall?.bias)}
                  >
                    {formatBiasLabel(selectedRow?.overall?.bias)}
                  </Tag>
                </div>
                <Text type="secondary">
                  Last updated:{' '}
                  {lastUpdated ? new Date(lastUpdated).toLocaleString() : '-'}
                </Text>
                {overviewData?.summary?.seasonality_month && (
                  <>
                    <br />
                    <Text type="secondary">
                      Seasonality month: {overviewData.summary.seasonality_month}
                    </Text>
                  </>
                )}
              </div>

              <div className="overview-drawer-stat-list">
                {componentRows(selectedRow).map((item) => (
                  <div className="overview-drawer-stat" key={item.label}>
                    <div className="overview-drawer-stat-title">
                      <Text strong>{item.label}</Text>
                      <Tag
                        color={getBiasColor(item.component?.bias)}
                        className={getBiasTagClassName(item.component?.bias)}
                        style={getBiasTagStyle(item.component?.bias)}
                      >
                        {formatBiasLabel(item.component?.bias)}
                      </Tag>
                    </div>
                    <Text strong style={{ color: getScoreColor(item.component?.score) }}>
                      Score {formatScore(item.component?.score)}
                    </Text>
                    <br />
                    <Text type="secondary">{item.detail || 'No detail available'}</Text>
                  </div>
                ))}
              </div>

              <Space direction="vertical" style={{ width: '100%' }}>
                <Button
                  block
                  className="overview-quick-link overview-quick-link--fundamental"
                  onClick={() =>
                    navigateToPair(`/fundamental/pair/${selectedRow.asset_symbol}`)
                  }
                >
                  Fundamental Pair Detail
                </Button>
                <Button
                  block
                  className="overview-quick-link overview-quick-link--cot"
                  onClick={() =>
                    navigateToPair(
                      `/sentimental/cot-positions/pairs/${selectedRow.asset_symbol}`
                    )
                  }
                >
                  COT Position Detail
                </Button>
                <Button
                  block
                  className="overview-quick-link overview-quick-link--retail"
                  onClick={() =>
                    navigateToPair(
                      `/sentimental/retail-sentiment/pairs/${selectedRow.asset_symbol}`
                    )
                  }
                >
                  Retail Sentiment Detail
                </Button>
                <Button
                  block
                  className="overview-quick-link overview-quick-link--news"
                  onClick={() => navigateToPair('/sentimental/news-sentiment')}
                >
                  News Sentiment
                </Button>
                <Button
                  block
                  className="overview-quick-link"
                  onClick={() => navigateToPair(`/seasonality/${selectedRow.asset_symbol}`)}
                >
                  Seasonality Analysis
                </Button>
              </Space>
            </Space>
          ) : (
            <Empty description="Select a pair from the overview table" />
          )}
        </Drawer>
      </div>
    </Sidebar>
  );
};

export default Overview;

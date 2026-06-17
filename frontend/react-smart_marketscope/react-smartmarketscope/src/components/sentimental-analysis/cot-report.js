import React, { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import Sidebar from '../sidebar';
import {
  fetchCotReportFiltersRequest,
  fetchCotReportRequest,
  setCotReportQuery,
} from '../../actions/cotReportActions';
import './cot-report.css';

const { Title, Text } = Typography;

const categoryLabels = {
  non_commercial: 'Non-Commercial',
  commercial: 'Commercial',
  nonreportable: 'Nonreportable',
};

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

const formatPercentage = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-';
  }

  return `${Number(value).toFixed(2)}%`;
};

const getBiasMeta = (netPosition) => {
  const absoluteNet = Math.abs(Number(netPosition || 0));

  if (absoluteNet === 0) {
    return { text: 'Neutral', color: 'gold' };
  }

  if (absoluteNet < 5000) {
    return {
      text: netPosition >= 0 ? 'Bullish' : 'Bearish',
      color: netPosition >= 0 ? 'green' : 'red',
    };
  }

  if (absoluteNet >= 60000) {
    return {
      text: netPosition >= 0 ? 'Strong Bullish' : 'Strong Bearish',
      color: netPosition >= 0 ? 'green' : 'red',
    };
  }

  return {
    text: netPosition >= 0 ? 'Bullish' : 'Bearish',
    color: netPosition >= 0 ? 'green' : 'red',
  };
};

const getNonCommercialNetPosition = (item) =>
  Number(item?.categories?.non_commercial?.net_position || 0);

const toCategoryCards = (categories = {}) =>
  Object.entries(categories).map(([key, category]) => ({
    key,
    label: categoryLabels[key] || key,
    netPosition: category?.net_position || 0,
    bias: getBiasMeta(category?.net_position || 0),
  }));

const CotReport = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { pair: routePair } = useParams();
  const [activeCategory, setActiveCategory] = useState('non_commercial');

  const normalizedPair = routePair?.toUpperCase() || null;
  const isPairPage = Boolean(normalizedPair);

  const {
    query,
    filtersMeta,
    filtersLoading,
    filtersError,
    reportData,
    loading,
    error,
    lastUpdated,
  } = useSelector((state) => state.cotReport || {});

  useEffect(() => {
    dispatch(fetchCotReportFiltersRequest());
  }, [dispatch]);

  useEffect(() => {
    const nextQuery = {
      asset: normalizedPair,
      report_date: query?.report_date || null,
    };

    dispatch(setCotReportQuery(nextQuery));
    dispatch(fetchCotReportRequest(nextQuery));
  }, [dispatch, normalizedPair, query?.report_date]);

  const items = useMemo(() => reportData?.items || [], [reportData]);
  const selectedItem = isPairPage ? items[0] : null;
  const selectedCategoryData = selectedItem?.categories?.[activeCategory];
  const supportedAssets = filtersMeta?.supported_assets || [];
  const categoryCards = selectedItem ? toCategoryCards(selectedItem.categories) : [];

  const nonCommercialItems = useMemo(
    () =>
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
      }),
    [items]
  );

  const overviewSummary = useMemo(() => {
    if (!nonCommercialItems.length) {
      return {
        mostBullish: null,
        mostBearish: null,
      };
    }

    const rankedBullish = nonCommercialItems
      .filter((item) => getNonCommercialNetPosition(item) > 0)
      .sort(
        (left, right) =>
          getNonCommercialNetPosition(right) - getNonCommercialNetPosition(left)
      );
    const rankedBearish = nonCommercialItems
      .filter((item) => getNonCommercialNetPosition(item) < 0)
      .sort(
        (left, right) =>
          getNonCommercialNetPosition(left) - getNonCommercialNetPosition(right)
      );

    return {
      mostBullish: rankedBullish[0] || null,
      mostBearish: rankedBearish[0] || null,
    };
  }, [nonCommercialItems]);

  const handleRefresh = () => {
    dispatch(
      fetchCotReportRequest({
        asset: normalizedPair,
        report_date: query?.report_date || null,
        refresh: true,
      })
    );
  };

  const handlePairSelect = (asset) => {
    if (!asset) {
      return;
    }

    navigate(`/sentimental/cot-positions/pairs/${asset}`);
  };

  const handleBackToOverview = () => {
    navigate('/sentimental/cot-positions');
  };

  const tableColumns = [
    {
      title: 'Pair',
      dataIndex: 'asset_symbol',
      key: 'asset_symbol',
      render: (value) => <Text strong>{formatPair(value)}</Text>,
    },
    {
      title: 'Bias',
      key: 'bias',
      render: (_, record) => {
        const meta = getBiasMeta(record?.categories?.non_commercial?.net_position || 0);

        return <Tag color={meta.color}>{meta.text}</Tag>;
      },
    },
    {
      title: 'Net Position',
      key: 'net_position',
      sorter: (left, right) =>
        (left?.categories?.non_commercial?.net_position || 0) -
        (right?.categories?.non_commercial?.net_position || 0),
      render: (_, record) => {
        const net = record?.categories?.non_commercial?.net_position || 0;

        return (
          <Text style={{ color: net >= 0 ? '#16a34a' : '#dc2626' }}>
            {net > 0 ? '+' : ''}
            {formatNumber(net)}
          </Text>
        );
      },
    },
    {
      title: 'Long %',
      key: 'long_percentage',
      render: (_, record) =>
        formatPercentage(record?.categories?.non_commercial?.long_percentage),
    },
    {
      title: 'Short %',
      key: 'short_percentage',
      render: (_, record) =>
        formatPercentage(record?.categories?.non_commercial?.short_percentage),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Button
          type="link"
          icon={<ArrowRightOutlined />}
          onClick={() =>
            navigate(`/sentimental/cot-positions/pairs/${record.asset_symbol}`)
          }
        >
          View categories
        </Button>
      ),
    },
  ];

  const tabItems = Object.entries(categoryLabels).map(([key, label]) => {
    const category = selectedItem?.categories?.[key];
    const netChange =
      (category?.change_long_contracts || 0) -
      (category?.change_short_contracts || 0);

    return {
      key,
      label,
      children: category ? (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={8}>
              <Card>
                <Statistic
                  title="Long Contracts"
                  value={category.long_contracts}
                  formatter={formatNumber}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={8}>
              <Card>
                <Statistic
                  title="Short Contracts"
                  value={category.short_contracts}
                  formatter={formatNumber}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={8}>
              <Card>
                <Statistic
                  title="Net Position"
                  value={category.net_position}
                  formatter={(value) =>
                    `${Number(value) > 0 ? '+' : ''}${formatNumber(value)}`
                  }
                  valueStyle={{
                    color: category.net_position >= 0 ? '#16a34a' : '#dc2626',
                  }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={12}>
              <Card>
                <Statistic
                  title="Weekly Long Change"
                  value={category.change_long_contracts}
                  formatter={(value) =>
                    `${Number(value) > 0 ? '+' : ''}${formatNumber(value)}`
                  }
                  valueStyle={{
                    color:
                      Number(category.change_long_contracts) >= 0
                        ? '#16a34a'
                        : '#dc2626',
                  }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={12}>
              <Card>
                <Statistic
                  title="Weekly Short Change"
                  value={category.change_short_contracts}
                  formatter={(value) =>
                    `${Number(value) > 0 ? '+' : ''}${formatNumber(value)}`
                  }
                  valueStyle={{
                    color:
                      Number(category.change_short_contracts) >= 0
                        ? '#16a34a'
                        : '#dc2626',
                  }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={12}>
              <Card>
                <Statistic
                  title="Weekly Net Change"
                  value={netChange}
                  formatter={(value) =>
                    `${Number(value) > 0 ? '+' : ''}${formatNumber(value)}`
                  }
                  valueStyle={{
                    color: netChange >= 0 ? '#16a34a' : '#dc2626',
                  }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="Position Share">
            <div style={{ marginBottom: 20 }}>
              <div className="cot-report-progress-label">
                <span>Long Position Share</span>
                <span>{formatPercentage(category.long_percentage)}</span>
              </div>
              <Progress
                percent={Math.min(Number(category.long_percentage || 0), 100)}
                strokeColor="#1677ff"
                showInfo={false}
              />
            </div>

            <div>
              <div className="cot-report-progress-label">
                <span>Short Position Share</span>
                <span>{formatPercentage(category.short_percentage)}</span>
              </div>
              <Progress
                percent={Math.min(Number(category.short_percentage || 0), 100)}
                strokeColor="#fa541c"
                showInfo={false}
              />
            </div>
          </Card>

          <Card title="Interpretation">
            <Space direction="vertical">
              <Tag color={getBiasMeta(category.net_position).color}>
                {getBiasMeta(category.net_position).text}
              </Tag>
              <Text>
                {label} traders currently show a{' '}
                <Text strong>
                  {category.net_position >= 0 ? 'net long' : 'net short'}
                </Text>{' '}
                bias on {formatPair(selectedItem.asset_symbol)}.
              </Text>
              <Text type="secondary">
                Long contracts: {formatNumber(category.long_contracts)}. Short
                contracts: {formatNumber(category.short_contracts)}. Weekly net
                change: {netChange > 0 ? '+' : ''}
                {formatNumber(netChange)}.
              </Text>
            </Space>
          </Card>
        </Space>
      ) : (
        <Empty className="cot-report-empty-block" description="No category data" />
      ),
    };
  });

  const renderHeader = () => (
    <Row gutter={[16, 16]} align="middle" justify="space-between">
      <Col xs={24} lg={12}>
        <Space direction="vertical" size={4}>
          <Title level={2} style={{ margin: 0 }}>
            {isPairPage
              ? `COT Pair Detail: ${formatPair(normalizedPair)}`
              : 'Commitments of Traders (COT)'}
          </Title>
          <Text type="secondary">
            Report date: {reportData?.report_date || '-'} | Latest sync:{' '}
            {reportData?.latest_stored_report_date || '-'}
          </Text>
        </Space>
      </Col>

      <Col xs={24} lg={12}>
        <div className="cot-report-toolbar">
          {isPairPage ? (
            <Button icon={<ArrowLeftOutlined />} onClick={handleBackToOverview}>
              Back to overview
            </Button>
          ) : null}

          <Select
            allowClear={!isPairPage}
            placeholder="Select pair"
            style={{ minWidth: 220 }}
            value={normalizedPair || undefined}
            options={supportedAssets.map((asset) => ({
              value: asset.symbol,
              label: `${formatPair(asset.symbol)} - ${asset.display_name}`,
            }))}
            onChange={handlePairSelect}
          />

          <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
            Refresh
          </Button>
        </div>
      </Col>
    </Row>
  );

  if (filtersError) {
    return (
      <Sidebar>
        <Alert message="Error" description={filtersError} type="error" showIcon />
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="cot-report-page">
        {renderHeader()}

        {error ? (
          <Alert message="Error" description={error} type="error" showIcon />
        ) : null}

        {filtersLoading || loading ? (
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 12 }}>Loading COT data...</div>
          </div>
        ) : !reportData || !items.length ? (
          <Empty description="No COT data available" />
        ) : isPairPage && selectedItem ? (
          <>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}>
                <Card className="cot-report-summary-card">
                  <span className="cot-report-summary-label">Primary Bias</span>
                  <span
                    className={`cot-report-stat ${
                      selectedCategoryData?.net_position >= 0
                        ? 'cot-report-stat--positive'
                        : 'cot-report-stat--negative'
                    }`}
                  >
                    {getBiasMeta(selectedCategoryData?.net_position || 0).text}
                  </span>
                  <Text type="secondary">
                    Based on the active {categoryLabels[activeCategory]} tab.
                  </Text>
                </Card>
              </Col>

              <Col xs={24} md={8}>
                <Card className="cot-report-summary-card">
                  <span className="cot-report-summary-label">Open Interest</span>
                  <span className="cot-report-stat">
                    {formatNumber(selectedItem.open_interest_all)}
                  </span>
                  <Text type="secondary">Total contracts across the market.</Text>
                </Card>
              </Col>

              <Col xs={24} md={8}>
                <Card className="cot-report-summary-card">
                  <span className="cot-report-summary-label">Last Refreshed</span>
                  <span className="cot-report-stat">
                    {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : '-'}
                  </span>
                </Card>
              </Col>
            </Row>

            <Card title="Category Snapshot">
              <div className="cot-report-category-grid">
                {categoryCards.map((card) => (
                  <div key={card.key} className="cot-report-category-card">
                    <div className="cot-report-category-title">
                      <span>{card.label}</span>
                      <Tag color={card.bias.color}>{card.bias.text}</Tag>
                    </div>
                    <Text
                      strong
                      style={{
                        color: card.netPosition >= 0 ? '#16a34a' : '#dc2626',
                        fontSize: 20,
                      }}
                    >
                      {card.netPosition > 0 ? '+' : ''}
                      {formatNumber(card.netPosition)}
                    </Text>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <Tabs
                activeKey={activeCategory}
                items={tabItems}
                onChange={setActiveCategory}
              />
            </Card>
          </>
        ) : (
          <>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card className="cot-report-summary-card">
                  <span className="cot-report-summary-label">Most Bullish</span>
                  <span className="cot-report-stat cot-report-stat--positive">
                    {overviewSummary.mostBullish
                      ? formatPair(overviewSummary.mostBullish.asset_symbol)
                      : '-'}
                  </span>
                  <Text type="secondary">
                    Net position:{' '}
                    {formatNumber(
                      overviewSummary.mostBullish?.categories?.non_commercial
                        ?.net_position
                    )}
                  </Text>
                </Card>
              </Col>

              <Col xs={24} md={12}>
                <Card className="cot-report-summary-card">
                  <span className="cot-report-summary-label">Most Bearish</span>
                  <span className="cot-report-stat cot-report-stat--negative">
                    {overviewSummary.mostBearish
                      ? formatPair(overviewSummary.mostBearish.asset_symbol)
                      : '-'}
                  </span>
                  <Text type="secondary">
                    Net position:{' '}
                    {formatNumber(
                      overviewSummary.mostBearish?.categories?.non_commercial
                        ?.net_position
                    )}
                  </Text>
                </Card>
              </Col>
            </Row>

            <Card
              title="Pair Overview"
              extra={
                <Text type="secondary">
                  Default lens: Non-Commercial positioning
                </Text>
              }
            >
              <Table
                rowKey="asset_symbol"
                columns={tableColumns}
                dataSource={nonCommercialItems}
                pagination={false}
              />
            </Card>
          </>
        )}
      </div>
    </Sidebar>
  );
};

export default CotReport;

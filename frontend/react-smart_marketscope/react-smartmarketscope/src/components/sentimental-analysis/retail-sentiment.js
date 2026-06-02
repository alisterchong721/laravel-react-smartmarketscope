import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useLocation, useParams } from 'react-router-dom';
import moment from 'moment-timezone';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import RefreshIcon from '@mui/icons-material/Refresh';
import FilterAltOffIcon from '@mui/icons-material/FilterAltOff';
import Sidebar from '../sidebar';
import {
  fetchRetailSentimentFiltersRequest,
  fetchRetailSentimentRequest,
  resetRetailSentimentQuery,
  setRetailSentimentQuery,
} from '../../actions/retailSentimentActions';
import './retail-sentiment.css';

const { Title, Text } = Typography;

const formatProviderTimeToMyt = (serverTimeText) => {
  if (!serverTimeText) {
    return null;
  }

  const parsedTime = moment.tz(
    serverTimeText,
    'DD-MM-YYYY HH:mm',
    'UTC'
  );

  if (!parsedTime.isValid()) {
    return null;
  }

  return parsedTime.tz('Asia/Kuala_Lumpur').format('DD-MM-YYYY HH:mm');
};

const RetailSentiment = () => {
  const dispatch = useDispatch();
  const location = useLocation();
  const { pair: routePair, broker: routeBroker } = useParams();
  const {
    query,
    filtersMeta,
    filtersLoading,
    filtersError,
    sentimentData,
    loading,
    error,
    lastUpdated,
  } = useSelector((state) => state.retailSentiment || {});

  useEffect(() => {
    dispatch(fetchRetailSentimentFiltersRequest());
  }, [dispatch]);

  useEffect(() => {
    if (!filtersMeta || loading) {
      return;
    }

    const normalizedRoutePair = routePair?.toUpperCase() || null;
    const normalizedRouteBroker = routeBroker?.toLowerCase() || null;
    const isBrokerRoute = location.pathname.includes('/brokers/');
    const isPairRoute = location.pathname.includes('/pairs/');

    const initialQuery = {
      group_by: isBrokerRoute
        ? 'brokers'
        : isPairRoute
          ? 'pairs'
          : query?.group_by || filtersMeta.default_group_by || 'pairs',
      pair:
        normalizedRoutePair ||
        query?.pair ||
        filtersMeta.default_pair ||
        'EURUSD',
      broker:
        normalizedRouteBroker ||
        query?.broker ||
        filtersMeta.default_broker ||
        filtersMeta.available_brokers?.[0]?.code ||
        null,
      pairs: isBrokerRoute ? [] : query?.pairs || [],
      brokers: isPairRoute ? [] : query?.brokers || [],
    };

    const queryChanged =
      query?.group_by !== initialQuery.group_by ||
      query?.pair !== initialQuery.pair ||
      query?.broker !== initialQuery.broker ||
      JSON.stringify(query?.pairs || []) !== JSON.stringify(initialQuery.pairs) ||
      JSON.stringify(query?.brokers || []) !==
        JSON.stringify(initialQuery.brokers);

    if (queryChanged || !sentimentData) {
      dispatch(setRetailSentimentQuery(initialQuery));
      dispatch(fetchRetailSentimentRequest(initialQuery));
    }
  }, [
    dispatch,
    filtersMeta,
    loading,
    location.pathname,
    query?.broker,
    query?.brokers,
    query?.group_by,
    query?.pair,
    query?.pairs,
    routeBroker,
    routePair,
    sentimentData,
  ]);

  const availableFilters = sentimentData?.available_filters || filtersMeta;
  const supportedPairs = availableFilters?.supported_pairs || [];
  const availableBrokers = availableFilters?.available_brokers || [];
  const items = sentimentData?.items || [];
  const summary = sentimentData?.summary;
  const selectedGroupBy = query?.group_by || 'pairs';
  const providerTimeInMyt = formatProviderTimeToMyt(
    sentimentData?.source?.server_time_text
  );
  const displayTitle =
    selectedGroupBy === 'pairs'
      ? sentimentData?.selected_pair || query?.pair || availableFilters?.default_pair
      : sentimentData?.selected_broker?.name ||
        sentimentData?.selected_broker?.code ||
        query?.broker ||
        availableFilters?.default_broker;

  const syncQueryAndFetch = (nextQuery, options = {}) => {
    dispatch(setRetailSentimentQuery(nextQuery));
    dispatch(
      fetchRetailSentimentRequest({
        ...nextQuery,
        ...(options.refresh ? { refresh: true } : {}),
      })
    );
  };

  const handleGroupByChange = (groupBy) => {
    const nextQuery =
      groupBy === 'pairs'
        ? {
            group_by: 'pairs',
            pair: query?.pair || availableFilters?.default_pair || 'EURUSD',
            broker: query?.broker || availableFilters?.default_broker || null,
            pairs: [],
            brokers: [],
          }
        : {
            group_by: 'brokers',
            pair: query?.pair || availableFilters?.default_pair || 'EURUSD',
            broker:
              query?.broker ||
              availableFilters?.default_broker ||
              availableBrokers?.[0]?.code ||
              null,
            pairs: [],
            brokers: [],
          };

    syncQueryAndFetch(nextQuery);
  };

  const handlePairSelection = (pair) => {
    if (selectedGroupBy === 'pairs') {
      syncQueryAndFetch({
        ...query,
        pair,
      });

      return;
    }

    const nextPairs = query?.pairs?.includes(pair)
      ? query.pairs.filter((item) => item !== pair)
      : [...(query?.pairs || []), pair];

    syncQueryAndFetch({
      ...query,
      pairs: nextPairs,
    });
  };

  const handleBrokerSelection = (brokerCode) => {
    if (selectedGroupBy === 'brokers') {
      syncQueryAndFetch({
        ...query,
        broker: brokerCode,
      });

      return;
    }

    const nextBrokers = query?.brokers?.includes(brokerCode)
      ? query.brokers.filter((item) => item !== brokerCode)
      : [...(query?.brokers || []), brokerCode];

    syncQueryAndFetch({
      ...query,
      brokers: nextBrokers,
    });
  };

  const handleRefresh = () => {
    syncQueryAndFetch(query, { refresh: true });
  };

  const handleClearFilters = () => {
    const resetQuery = {
      group_by: availableFilters?.default_group_by || 'pairs',
      pair: availableFilters?.default_pair || 'EURUSD',
      broker:
        availableFilters?.default_broker || availableBrokers?.[0]?.code || null,
      pairs: [],
      brokers: [],
    };

    dispatch(resetRetailSentimentQuery());
    syncQueryAndFetch(resetQuery);
  };

  const isPairButtonActive = (pair) =>
    selectedGroupBy === 'pairs'
      ? (query?.pair || '').toUpperCase() === pair
      : (query?.pairs || []).includes(pair);

  const isBrokerButtonActive = (brokerCode) =>
    selectedGroupBy === 'brokers'
      ? (query?.broker || '').toLowerCase() === brokerCode.toLowerCase()
      : (query?.brokers || []).includes(brokerCode);

  const renderSentimentBar = (item, index) => {
    const buyWidth = Math.min(Math.max(item.buy_percentage || 0, 0), 100);
    const sellWidth = Math.min(Math.max(item.sell_percentage || 0, 0), 100);
    const label =
      selectedGroupBy === 'pairs' ? item.broker_name : item.pair?.toUpperCase();

    return (
      <div
        key={`${item.broker_code || item.pair}-${index}`}
        className="retail-sentiment-row"
      >
        <div className="retail-sentiment-row__label">{label}</div>
        <div className="retail-sentiment-row__bar">
          <div className="retail-sentiment-row__center-line" />
          <div
            className="retail-sentiment-row__segment retail-sentiment-row__segment--buy"
            style={{ width: `${buyWidth}%` }}
          >
            <span>{buyWidth.toFixed(2)}%</span>
          </div>
          <div
            className="retail-sentiment-row__segment retail-sentiment-row__segment--sell"
            style={{ width: `${sellWidth}%` }}
          >
            <span>{sellWidth.toFixed(2)}%</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Sidebar>
      <div className="retail-sentiment-page">
        <Row justify="space-between" align="middle" gutter={[16, 16]}>
          <Col xs={24} lg={15}>
            <Space direction="vertical" size={4}>
              <Title level={2} style={{ margin: 0 }}>
                Retail Sentiment
              </Title>
              <Space wrap>
                <Tag color="blue">
                  Grouped by {selectedGroupBy === 'pairs' ? 'Pairs' : 'Brokers'}
                </Tag>
                {displayTitle ? <Tag color="gold">{displayTitle}</Tag> : null}
                {sentimentData?.source?.provider ? (
                  <Tag>{sentimentData.source.provider}</Tag>
                ) : null}
              </Space>
              {providerTimeInMyt ? (
                <Text type="secondary">
                  Last provider update (MYT): {providerTimeInMyt}
                </Text>
              ) : lastUpdated ? (
                <Text type="secondary">
                  Last updated: {new Date(lastUpdated).toLocaleString()}
                </Text>
              ) : null}
            </Space>
          </Col>

          <Col xs={24} lg={9}>
            <Row gutter={[12, 12]} justify="end">
              <Col xs={12} sm={8}>
                <Button
                  block
                  type="primary"
                  icon={<RefreshIcon />}
                  loading={loading}
                  onClick={handleRefresh}
                >
                  Refresh
                </Button>
              </Col>
              <Col xs={12} sm={10}>
                <Button
                  block
                  icon={<FilterAltOffIcon />}
                  onClick={handleClearFilters}
                >
                  Clear Filters
                </Button>
              </Col>
            </Row>
          </Col>
        </Row>

        {filtersError ? (
          <Alert
            style={{ marginTop: 20 }}
            type="error"
            showIcon
            message="Unable to load filters"
            description={filtersError}
          />
        ) : null}

        {error ? (
          <Alert
            style={{ marginTop: 20 }}
            type="error"
            showIcon
            message="Unable to load sentiment data"
            description={error}
          />
        ) : null}

        <Row gutter={[24, 24]} style={{ marginTop: 20 }}>
          <Col xs={24} xl={17}>
            <Card className="retail-sentiment-card">
              {loading && !sentimentData ? (
                <div className="retail-sentiment-loading">
                  <Spin size="large" />
                </div>
              ) : items.length > 0 ? (
                <div className="retail-sentiment-chart">
                  <div className="retail-sentiment-chart__title">
                    {displayTitle}
                  </div>
                  {items.map(renderSentimentBar)}

                  {summary ? (
                    <div className="retail-sentiment-summary">
                      <div className="retail-sentiment-summary__divider" />
                      <div className="retail-sentiment-row retail-sentiment-row--summary">
                        <div className="retail-sentiment-row__label">Average</div>
                        <div className="retail-sentiment-row__bar">
                          <div className="retail-sentiment-row__center-line" />
                          <div
                            className="retail-sentiment-row__segment retail-sentiment-row__segment--buy"
                            style={{
                              width: `${summary.average_buy_percentage}%`,
                            }}
                          >
                            <span>{summary.average_buy_percentage.toFixed(2)}%</span>
                          </div>
                          <div
                            className="retail-sentiment-row__segment retail-sentiment-row__segment--sell"
                            style={{
                              width: `${summary.average_sell_percentage}%`,
                            }}
                          >
                            <span>
                              {summary.average_sell_percentage.toFixed(2)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <Empty description="No retail sentiment rows available" />
              )}
            </Card>
          </Col>

          <Col xs={24} xl={7}>
            <Card className="retail-sentiment-card retail-sentiment-filters">
              <div className="retail-sentiment-filter-group">
                <div className="retail-sentiment-filter-group__title">Group By</div>
                <div className="retail-sentiment-filter-group__options">
                  <Button
                    type={selectedGroupBy === 'pairs' ? 'primary' : 'default'}
                    onClick={() => handleGroupByChange('pairs')}
                  >
                    Pairs
                  </Button>
                  <Button
                    type={selectedGroupBy === 'brokers' ? 'primary' : 'default'}
                    onClick={() => handleGroupByChange('brokers')}
                  >
                    Brokers
                  </Button>
                </div>
              </div>

              <div className="retail-sentiment-filter-group">
                <div className="retail-sentiment-filter-group__title">
                  {selectedGroupBy === 'pairs' ? 'Symbol' : 'Pairs'}
                </div>
                <div className="retail-sentiment-filter-group__options retail-sentiment-filter-group__options--grid">
                  {supportedPairs.map((pair) => (
                    <Button
                      key={pair}
                      type={isPairButtonActive(pair) ? 'primary' : 'default'}
                      onClick={() => handlePairSelection(pair)}
                    >
                      {pair}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="retail-sentiment-filter-group">
                <div className="retail-sentiment-filter-group__title">
                  {selectedGroupBy === 'pairs' ? 'Brokers' : 'Symbol'}
                </div>
                <div className="retail-sentiment-filter-group__options retail-sentiment-filter-group__options--grid">
                  {availableBrokers.map((broker) => (
                    <Button
                      key={broker.code}
                      type={
                        isBrokerButtonActive(broker.code) ? 'primary' : 'default'
                      }
                      onClick={() => handleBrokerSelection(broker.code)}
                    >
                      {broker.name}
                    </Button>
                  ))}
                </div>
              </div>

              {filtersLoading ? (
                <div className="retail-sentiment-filters__loading">
                  <Spin size="small" />
                </div>
              ) : null}
            </Card>
          </Col>
        </Row>
      </div>
    </Sidebar>
  );
};

export default RetailSentiment;

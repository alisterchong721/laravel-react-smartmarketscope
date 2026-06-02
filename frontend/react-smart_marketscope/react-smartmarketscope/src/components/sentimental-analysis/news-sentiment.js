import React, { useEffect, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  Alert,
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
  Tag,
  Typography,
} from 'antd';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
} from '@ant-design/icons';
import Sidebar from '../sidebar';
import {
  fetchNewsSentimentFiltersRequest,
  fetchNewsSentimentRequest,
  setNewsSentimentQuery,
} from '../../actions/newsSentimentActions';
import './news-sentiment.css';

const { Title, Paragraph, Text } = Typography;

const getSentimentMeta = (score) => {
  if (score >= 70) {
    return { label: 'Strong Bullish', color: 'green' };
  }

  if (score >= 55) {
    return { label: 'Bullish', color: 'lime' };
  }

  if (score >= 45) {
    return { label: 'Neutral', color: 'gold' };
  }

  if (score >= 30) {
    return { label: 'Bearish', color: 'orange' };
  }

  return { label: 'Strong Bearish', color: 'red' };
};

const clampScore = (value) => {
  const numeric = Number(value);

  if (Number.isNaN(numeric)) {
    return 50;
  }

  return Math.max(0, Math.min(100, Math.round(numeric)));
};

const formatDateTime = (value) => {
  if (!value) {
    return 'No data';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-MY', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

const titleCase = (value) =>
  String(value || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .trim();

const normalizeScoreFromItem = (item) => {
  if (item.sentiment_score !== undefined && item.sentiment_score !== null) {
    return clampScore(item.sentiment_score);
  }

  if (item.impact_score !== undefined && item.impact_score !== null) {
    return clampScore(item.impact_score);
  }

  const direction = String(
    item.sentiment ||
      item.sentiment_label ||
      item.sentiment_direction ||
      item.direction ||
      ''
  ).toLowerCase();

  if (direction === 'bullish') {
    return 75;
  }

  if (direction === 'bearish') {
    return 25;
  }

  return 50;
};

const normalizeAssetFromItem = (item) =>
  (
    item.asset_symbol ||
    item.asset ||
    item.symbol ||
    item.ticker ||
    item.currency_pair ||
    item.pair ||
    item.market ||
    'Unknown'
  ).toUpperCase();

const normalizeArticle = (item, index) => {
  const score = normalizeScoreFromItem(item);
  const source =
    item.source_name ||
    item.source ||
    item.publisher ||
    item.domain ||
    'Unknown source';
  const asset = normalizeAssetFromItem(item);
  const headline = item.title || item.headline || null;
  const sentimentText =
    item.sentiment ||
    item.sentiment_label ||
    item.sentiment_direction ||
    item.direction ||
    getSentimentMeta(score).label;

  return {
    key: item.id || item.uuid || item.url || `${asset}-${index}`,
    headline,
    hasHeadline: Boolean(headline),
    source,
    publishedAt:
      item.published_at || item.publishedAt || item.created_at || item.updated_at || null,
    asset,
    score,
    tone: titleCase(sentimentText),
    summary:
      item.summary ||
      item.description ||
      item.snippet ||
      item.reasoning ||
      item.explanation ||
      'No article summary available.',
    url: item.url || item.article_url || null,
  };
};

const NewsSentiment = () => {
  const dispatch = useDispatch();
  const { query, filtersMeta, filtersLoading, filtersError, newsData, loading, error } =
    useSelector((state) => state.newsSentiment || {});

  const queryAssetsKey = JSON.stringify(query?.assets || []);
  const defaultLimit = filtersMeta?.default_limit || 20;

  useEffect(() => {
    dispatch(fetchNewsSentimentFiltersRequest());
  }, [dispatch]);

  useEffect(() => {
    const nextQuery = {
      assets: query?.assets || [],
      status: 'completed',
      limit: query?.limit || defaultLimit,
    };

    dispatch(setNewsSentimentQuery(nextQuery));
    dispatch(fetchNewsSentimentRequest(nextQuery));
  }, [
    defaultLimit,
    dispatch,
    query?.assets,
    queryAssetsKey,
    query?.limit,
  ]);

  const summary = newsData?.summary || {};
  const availableFilters = newsData?.available_filters || filtersMeta || {};
  const selectedAssets = query?.assets || newsData?.selected_assets || [];
  const selectedAsset = selectedAssets[0] || 'ALL';

  const normalizedArticles = useMemo(
    () => (newsData?.items || []).map((item, index) => normalizeArticle(item, index)),
    [newsData?.items]
  );

  const assetBreakdown = useMemo(() => {
    const seed = (availableFilters?.supported_assets || []).reduce((accumulator, asset) => {
      accumulator[asset.symbol] = {
        key: asset.symbol,
        asset: asset.symbol,
        coverage: 0,
        avgScore: null,
        bullishCount: 0,
        bearishCount: 0,
        neutralCount: 0,
        latestPublishedAt: null,
      };

      return accumulator;
    }, {});

    normalizedArticles.forEach((article) => {
      const existing = seed[article.asset] || {
        key: article.asset,
        asset: article.asset,
        coverage: 0,
        avgScore: null,
        bullishCount: 0,
        bearishCount: 0,
        neutralCount: 0,
        latestPublishedAt: null,
        scoreTotal: 0,
      };

      existing.coverage += 1;
      existing.scoreTotal = (existing.scoreTotal || 0) + article.score;

      if (article.score >= 55) {
        existing.bullishCount += 1;
      } else if (article.score <= 45) {
        existing.bearishCount += 1;
      } else {
        existing.neutralCount += 1;
      }

      if (!existing.latestPublishedAt || new Date(article.publishedAt) > new Date(existing.latestPublishedAt)) {
        existing.latestPublishedAt = article.publishedAt;
      }

      seed[article.asset] = existing;
    });

    return Object.values(seed).map((entry) => {
      const avgScore =
        entry.coverage > 0
          ? clampScore((entry.scoreTotal || 0) / entry.coverage)
          : null;
      const netBias = avgScore === null ? 'No data' : getSentimentMeta(avgScore).label;

      return {
        ...entry,
        score: avgScore,
        dominant_tone: netBias,
        scoreTotal: undefined,
      };
    });
  }, [availableFilters?.supported_assets, normalizedArticles]);

  const filteredArticles = useMemo(() => {
    if (selectedAsset === 'ALL') {
      return normalizedArticles;
    }

    return normalizedArticles.filter((article) => article.asset === selectedAsset);
  }, [normalizedArticles, selectedAsset]);

  const filteredAssetBreakdown = useMemo(() => {
    if (selectedAsset === 'ALL') {
      return assetBreakdown;
    }

    return assetBreakdown.filter((item) => item.asset === selectedAsset);
  }, [assetBreakdown, selectedAsset]);

  const assetOptions = useMemo(
    () => [
      { label: 'All Assets', value: 'ALL' },
      ...((availableFilters?.supported_assets || [])
        .map((item) => ({
          label: item.symbol,
          value: item.symbol,
        })) || []),
    ],
    [availableFilters?.supported_assets]
  );

  const dominantDriver = useMemo(() => {
    const topAsset = filteredAssetBreakdown
      .filter((item) => item.coverage > 0 && item.score !== null)
      .sort((left, right) => right.coverage - left.coverage)[0];

    if (!topAsset) {
      return selectedAsset === 'ALL'
        ? 'No news sentiment data available yet.'
        : `No news sentiment data available yet for ${selectedAsset}.`;
    }

    return `${topAsset.asset} has the heaviest article coverage in the current feed.`;
  }, [filteredAssetBreakdown, selectedAsset]);

  const overallScore = clampScore(summary.average_impact_score || 0);
  const bullishShare =
    summary.total_items > 0
      ? Math.round(((summary.bullish_count || 0) / summary.total_items) * 100)
      : 0;
  const neutralShare =
    summary.total_items > 0
      ? Math.round(((summary.neutral_count || 0) / summary.total_items) * 100)
      : 0;
  const bearishShare =
    summary.total_items > 0
      ? Math.round(((summary.bearish_count || 0) / summary.total_items) * 100)
      : 0;

  const assetColumns = [
    {
      title: 'Asset',
      dataIndex: 'asset',
      key: 'asset',
      render: (value) => <Text strong>{value}</Text>,
    },
    {
      title: 'Sentiment',
      key: 'score',
      render: (_, record) => {
        if (record.score === null) {
          return <Text type="secondary">No data</Text>;
        }

        const meta = getSentimentMeta(record.score);

        return (
          <Space direction="vertical" size={4}>
            <Tag color={meta.color}>{meta.label}</Tag>
            <Progress
              percent={record.score}
              size="small"
              showInfo={false}
              strokeColor={record.score >= 50 ? '#16a34a' : '#dc2626'}
            />
          </Space>
        );
      },
    },
    {
      title: 'Shift',
      key: 'change',
      render: (_, record) => {
        if (record.score === null) {
          return <Text type="secondary">No data</Text>;
        }

        const positive = record.score >= 50;

        return (
          <Text style={{ color: positive ? '#15803d' : '#b91c1c' }}>
            {positive ? <ArrowUpOutlined /> : <ArrowDownOutlined />}{' '}
            {Math.abs(record.score - 50)} pts
          </Text>
        );
      },
    },
    {
      title: 'Coverage',
      dataIndex: 'coverage',
      key: 'coverage',
      render: (value) => `${value} article${value === 1 ? '' : 's'}`,
    },
    {
      title: 'Driver',
      dataIndex: 'dominant_tone',
      key: 'dominant_tone',
      render: (value) => value || 'No data',
    },
  ];

  const syncMeta = newsData?.sync;

  const handleAssetChange = (value) => {
    const nextQuery = {
      ...query,
      assets: value === 'ALL' ? [] : [value],
    };

    dispatch(setNewsSentimentQuery(nextQuery));
    dispatch(fetchNewsSentimentRequest(nextQuery));
  };

  return (
    <Sidebar>
      <div className="news-sentiment-page">
        <div className="news-sentiment-hero">
          <div>
            <Title level={2} style={{ marginBottom: 8 }}>
              News Sentiment Dashboard
            </Title>
            <Paragraph className="news-sentiment-hero__text">
              Live from your Laravel endpoint. The pair summary, overall counts,
              and article list now all come from the same API response so the UI
              stays consistent when data is empty or filtered.
            </Paragraph>
            <Space wrap>
              <Select
                options={assetOptions}
                value={selectedAsset}
                onChange={handleAssetChange}
                style={{ width: 180 }}
              />
            </Space>
          </div>

          <div className="news-sentiment-score">
            <div className="news-sentiment-score__ring">
              <Progress
                type="circle"
                percent={overallScore}
                strokeColor={overallScore >= 50 ? '#16a34a' : '#dc2626'}
                trailColor="#e5e7eb"
                format={() => `${overallScore}`}
              />
            </div>
            <div>
              <Text type="secondary">Overall Market Mood</Text>
              <div className="news-sentiment-score__label">
                {summary.total_items > 0 ? getSentimentMeta(overallScore).label : 'No data'}
              </div>
              <div className="news-sentiment-score__meta">
                Confidence {Math.round(summary.average_confidence_score || 0)}% • Updated{' '}
                {formatDateTime(syncMeta?.fetched_at || summary.latest_published_at)}
              </div>
            </div>
          </div>
        </div>

        {filtersLoading && (
          <Alert type="info" showIcon message="Loading news sentiment filters..." />
        )}
        {filtersError && (
          <Alert type="warning" showIcon message={filtersError} />
        )}
        {error && <Alert type="error" showIcon message={error} />}

        <Alert
          type="info"
          showIcon
          message={`Dominant driver: ${dominantDriver}`}
          className="news-sentiment-alert"
        />

        <Row gutter={[16, 16]}>
          <Col xs={24} md={12} xl={6}>
            <Card className="news-sentiment-stat">
              <Statistic
                title="Articles Analyzed"
                value={summary.total_items || 0}
              />
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card className="news-sentiment-stat">
              <Statistic
                title="Bullish Share"
                value={bullishShare}
                suffix="%"
                valueStyle={{ color: '#15803d' }}
              />
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card className="news-sentiment-stat">
              <Statistic
                title="Neutral Share"
                value={neutralShare}
                suffix="%"
              />
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card className="news-sentiment-stat">
              <Statistic
                title="Bearish Share"
                value={bearishShare}
                suffix="%"
                valueStyle={{ color: '#b91c1c' }}
              />
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
          <Col xs={24}>
            <Card title="Pair Sentiment Matrix">
              {loading && !newsData ? (
                <div className="news-sentiment-loading">
                  <Spin />
                </div>
              ) : (
                <Table
                  columns={assetColumns}
                  dataSource={filteredAssetBreakdown}
                  pagination={false}
                  locale={{ emptyText: 'No asset sentiment data available' }}
                  rowClassName={(record) =>
                    record.asset === selectedAsset ? 'news-sentiment-row--active' : ''
                  }
                />
              )}
            </Card>
          </Col>
        </Row>

        <Card title="Recent Articles and Explainability" style={{ marginTop: 16 }}>
          {loading && !newsData ? (
            <div className="news-sentiment-loading">
              <Spin />
            </div>
          ) : filteredArticles.length === 0 ? (
            <Empty
              description={
                selectedAsset === 'ALL'
                  ? 'No news sentiment article data available yet'
                  : `No news sentiment article data for ${selectedAsset}`
              }
            />
          ) : (
            <Row gutter={[16, 16]}>
              {filteredArticles.map((article) => (
                <Col xs={24} lg={8} key={article.key}>
	                  <div className="news-sentiment-article">
	                    <div className="news-sentiment-article__meta">
	                      {article.source !== 'Unknown source' && (
	                        <Tag color="blue">{article.source}</Tag>
	                      )}
                      <Tag color="default">{article.asset}</Tag>
                      <Tag color={getSentimentMeta(article.score).color}>
	                        {article.tone}
	                      </Tag>
	                    </div>
	                    {article.hasHeadline && (
	                      <Title level={5}>
	                        {article.url ? (
	                          <a href={article.url} target="_blank" rel="noreferrer">
	                            {article.headline}
	                          </a>
	                        ) : (
	                          article.headline
	                        )}
	                      </Title>
	                    )}
	                    <Paragraph>{article.summary}</Paragraph>
                    <div className="news-sentiment-article__footer">
                      <Text type="secondary">{formatDateTime(article.publishedAt)}</Text>
                      <Text strong>Score {article.score}</Text>
                    </div>
                  </div>
                </Col>
              ))}
            </Row>
          )}
        </Card>
      </div>
    </Sidebar>
  );
};

export default NewsSentiment;

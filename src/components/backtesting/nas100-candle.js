import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Button,
  Descriptions,
  Input,
  Modal,
  Select,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  CheckCircleOutlined,
  EyeOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import Sidebar from '../sidebar';
import HistoricalCandleChart from '../research/historical-candle-chart';
import { apiPath } from '../../config/api';
import {
  enrichD1SweepsWithM1Status,
  filterD1Sweeps,
  mergeM1WindowWithSetupRoles,
  sortD1SweepsNewestFirst,
  uniqueValues,
} from './nas100-candle-utils';
import './nas100-candle.css';

const { Title, Text } = Typography;
const EMPTY_FILTERS = {
  query: '', year: '', direction: '', h4Status: '', setupState: '',
};

const displayNumber = (value) => (
  value === null || value === undefined || value === ''
    ? '—'
    : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
);

const requestHeaders = () => {
  const token = localStorage.getItem('token');
  return {
    Accept: 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const directionTag = (direction) => (
  <Tag color={direction === 'BULLISH' ? 'green' : 'red'}>{direction}</Tag>
);

const H4_STATUS = {
  CONFIRMED: { color: 'green', label: 'H4 activated intrabar' },
  EXPIRED: { color: 'default', label: 'Expired' },
  INCOMPLETE_SOURCE_WINDOW: { color: 'gold', label: 'Source window incomplete' },
};

const BREAKER_FVG_LABELS = {
  M1_BREAKER_FVG_2R: 'Full-wick breaker + FVG · 2R',
  M1_BREAKER_FVG_2_5R: 'Full-wick breaker + FVG · 2.5R',
  M1_INTRABAR_H4_BREAKER_FVG_2R: 'Intrabar H4 breaker + FVG · 2R',
  M1_INTRABAR_H4_BREAKER_FVG_2_5R: 'Intrabar H4 breaker + FVG · 2.5R',
};

const LTF_OUTCOME = {
  WIN_2R: { color: 'green', label: '2R reached' },
  WIN_2_5R: { color: 'green', label: '2.5R reached' },
  LOSS_1R: { color: 'red', label: 'Stop first' },
  AMBIGUOUS_ADVERSE_FIRST: { color: 'volcano', label: 'Ambiguous · stop first' },
  TIMEOUT: { color: 'gold', label: 'Expired at H4 interval end' },
  NOT_APPLICABLE: { color: 'default', label: 'No entry setup' },
};

const ltfOutcomeTag = (value) => {
  const presentation = LTF_OUTCOME[value] || { color: 'default', label: value || '—' };
  return <Tag color={presentation.color}>{presentation.label}</Tag>;
};

const signedR = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return `${number > 0 ? '+' : ''}${number.toFixed(3)}R`;
};

const h4StatusTag = (status) => {
  const presentation = H4_STATUS[status] || { color: 'default', label: status || '—' };
  return <Tag color={presentation.color}>{presentation.label}</Tag>;
};

const Nas100Candle = () => {
  const [index, setIndex] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedBreakerConfiguration, setSelectedBreakerConfiguration] = useState('');
  const [error, setError] = useState('');

  const loadSweeps = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(apiPath('/research/d1-h4-sweep-review'), {
        headers: requestHeaders(),
      });
      const payload = response.data?.data;
      if (!payload || !Array.isArray(payload.sweeps)) {
        throw new Error('The corrected D1 sweep census is invalid.');
      }
      if (payload.h4ConfirmedCount !== payload.sweeps.length || payload.d1H4Only !== false) {
        throw new Error('The D1-to-H4 sweep census does not reconcile.');
      }
      setIndex(payload);
    } catch (requestError) {
      setError(
        requestError.response?.data?.message
        || requestError.message
        || 'Unable to load the corrected D1 sweep census.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSweeps();
  }, []);

  const sweeps = useMemo(() => index?.sweeps || [], [index]);
  const breakerComparison = index?.breakerFvgComparison || null;
  const breakerSummaries = useMemo(() => breakerComparison?.summaries || [], [breakerComparison]);
  const breakerEventByHash = useMemo(() => new Map(
    (breakerComparison?.events || []).map((event) => [event.sweepHash, event])
  ), [breakerComparison]);
  const enrichedSweeps = useMemo(() => enrichD1SweepsWithM1Status(
    sweeps,
    breakerComparison?.events || []
  ), [breakerComparison, sweeps]);
  const visibleSweeps = useMemo(() => sortD1SweepsNewestFirst(
    filterD1Sweeps(enrichedSweeps, filters)
  ), [enrichedSweeps, filters]);
  const years = useMemo(() => (
    uniqueValues(sweeps, 'year').sort((left, right) => Number(right) - Number(left))
  ), [sweeps]);

  const setFilter = (key, value) => {
    setFilters((current) => ({ ...current, [key]: value || '' }));
  };

  const openSweep = async (sweep) => {
    setDetailLoading(true);
    setError('');
    setDetail({ loadingSummary: sweep });
    try {
      const response = await axios.get(
        apiPath(`/research/d1-h4-sweep-review/${sweep.sweepHash}`),
        { headers: requestHeaders() }
      );
      const nextDetail = response.data?.data || null;
      setDetail(nextDetail);
      const firstCandidate = nextDetail?.breakerFvg?.configurations?.find(
        (configuration) => configuration.candidateStatus === 'VALID_CANDIDATE'
      );
      setSelectedBreakerConfiguration(firstCandidate?.configuration || '');
    } catch (requestError) {
      setDetail(null);
      setError(
        requestError.response?.data?.message
        || requestError.message
        || 'Unable to load the selected D1-to-H4 sweep.'
      );
    } finally {
      setDetailLoading(false);
    }
  };

  const columns = [
    {
      title: 'D1 intrabar activation',
      dataIndex: 'confirmationTime',
      key: 'confirmationTime',
      width: 205,
      render: (value, record) => (
        <Button
          type="link"
          className="nas100-candle-period-button"
          onClick={() => openSweep(record)}
        >
          <strong>{value}</strong>
          <small>View D1 + H4 candles</small>
        </Button>
      ),
    },
    {
      title: 'D1 swing bias',
      dataIndex: 'direction',
      key: 'direction',
      width: 130,
      render: directionTag,
    },
    {
      title: 'H4 stage',
      dataIndex: 'h4Status',
      key: 'h4Status',
      width: 190,
      render: h4StatusTag,
    },
    {
      title: 'H4 intrabar activation',
      dataIndex: 'h4ConfirmationTime',
      key: 'h4ConfirmationTime',
      width: 190,
      render: (value) => value || '—',
    },
    {
      title: 'H4 interval expires',
      dataIndex: 'h4WindowExpiry',
      key: 'h4WindowExpiry',
      width: 190,
      render: (value) => value || '—',
    },
    {
      title: 'H4 wick beyond',
      dataIndex: 'h4Excursion',
      key: 'h4Excursion',
      width: 145,
      render: displayNumber,
    },
    {
      title: 'M1 breaker + FVG',
      key: 'breakerFvg',
      width: 170,
      render: (_, record) => {
        const lower = breakerEventByHash.get(record.sweepHash);
        if (!lower) return record.h4Status === 'CONFIRMED' ? '—' : 'Not eligible';
        return `${lower.filledConfigurationCount} filled / ${lower.candidateConfigurationCount} formed`;
      },
    },
    {
      title: '',
      key: 'view',
      fixed: 'right',
      width: 110,
      render: (_, record) => (
        <Button icon={<EyeOutlined />} onClick={() => openSweep(record)}>Review</Button>
      ),
    },
  ];

  const selectedSummary = detail?.summary || detail?.loadingSummary || null;
  const selectedBreaker = detail?.breakerFvg?.configurations?.find(
    (configuration) => configuration.configuration === selectedBreakerConfiguration
  ) || null;
  const noBreakerFormed = Boolean(detail?.breakerFvg)
    && !(detail.breakerFvg.configurations || []).some(
      (configuration) => configuration.candidateStatus === 'VALID_CANDIDATE'
    );
  const noBreakerFilled = Boolean(detail?.breakerFvg)
    && !(detail.breakerFvg.configurations || []).some(
      (configuration) => configuration.fillStatus === 'FILLED'
    );
  const selectedBreakerDisplayCandles = selectedBreaker
    ? mergeM1WindowWithSetupRoles(
      detail?.m1WindowReview?.candles || selectedBreaker.candles || [],
      selectedBreaker.candles || []
    )
    : [];

  const breakerSummaryColumns = [
    {
      title: 'Test',
      dataIndex: 'configuration',
      key: 'configuration',
      width: 260,
      render: (value) => BREAKER_FVG_LABELS[value] || value,
    },
    { title: 'Candidates', dataIndex: 'valid_candidate_count', key: 'valid_candidate_count', width: 110 },
    { title: 'Fills', dataIndex: 'proven_fill_count', key: 'proven_fill_count', width: 90 },
    { title: 'Target wins', dataIndex: 'win_count', key: 'win_count', width: 105 },
    { title: 'Stops', dataIndex: 'loss_1r_count', key: 'loss_1r_count', width: 90 },
    { title: 'Expired', dataIndex: 'timeout_count', key: 'timeout_count', width: 90 },
    {
      title: 'Gross expectancy',
      dataIndex: 'gross_expectancy_r',
      key: 'gross_expectancy_r',
      width: 150,
      render: (value) => <Text type={Number(value) >= 0 ? 'success' : 'danger'}>{signedR(value)}</Text>,
    },
    {
      title: 'Medium-cost expectancy',
      dataIndex: 'normalized_medium_cost_net_expectancy_r',
      key: 'normalized_medium_cost_net_expectancy_r',
      width: 185,
      render: (value) => <Text type={Number(value) >= 0 ? 'success' : 'danger'}>{signedR(value)}</Text>,
    },
    {
      title: 'Decision',
      key: 'decision',
      width: 120,
      render: () => <Tag color="red">Rejected</Tag>,
    },
  ];

  const breakerDetailColumns = [
    {
      title: 'Test',
      dataIndex: 'configuration',
      key: 'configuration',
      width: 250,
      render: (value) => BREAKER_FVG_LABELS[value] || value,
    },
    {
      title: 'Setup',
      dataIndex: 'candidateStatus',
      key: 'candidateStatus',
      width: 120,
      render: (value) => <Tag color={value === 'VALID_CANDIDATE' ? 'blue' : 'default'}>{value === 'VALID_CANDIDATE' ? 'Formed' : 'None'}</Tag>,
    },
    {
      title: 'Fill',
      dataIndex: 'fillStatus',
      key: 'fillStatus',
      width: 105,
      render: (value) => <Tag color={value === 'FILLED' ? 'cyan' : 'default'}>{value === 'FILLED' ? 'Filled' : value === 'NO_FILL' ? 'No fill' : '—'}</Tag>,
    },
    { title: 'Outcome', dataIndex: 'outcome', key: 'outcome', width: 185, render: ltfOutcomeTag },
    { title: 'Gross', dataIndex: 'grossR', key: 'grossR', width: 100, render: signedR },
    { title: 'Medium cost', dataIndex: 'normalizedMediumCostNetR', key: 'normalizedMediumCostNetR', width: 120, render: signedR },
    {
      title: '',
      key: 'review',
      width: 100,
      render: (_, record) => (
        <Button
          size="small"
          disabled={record.candidateStatus !== 'VALID_CANDIDATE'}
          onClick={() => setSelectedBreakerConfiguration(record.configuration)}
        >
          Chart
        </Button>
      ),
    },
  ];

  return (
    <Sidebar>
      <div className="nas100-candle-page" data-testid="nas100-candle-page">
        <div className="nas100-candle-heading">
          <div>
            <Text className="nas100-candle-eyebrow">D1 → H4 → M1 breaker/FVG research · read only</Text>
            <Title level={2}>NAS100 D1 + H4 Sweep to M1 Breaker</Title>
            <Text type="secondary">
              D1 activates intrabar → H4 activates inside that D1 candle → M1 breaker + FVG inside that H4 candle only
            </Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={loadSweeps} loading={loading}>Refresh</Button>
        </div>

        <Alert
          type="info"
          showIcon
          title="Nested intrabar clock: D1 → H4 → M1"
          description="The detector does not wait for a D1 or H4 candle to close. A completed M1 close may activate the developing D1 sweep; the same-direction H4 sweep must then activate inside that D1 candle. M1 breaker + displacement-FVG entries are searched strictly after H4 activation and only until that H4 candle ends. Prior close-confirmed trials remain archived but are invalid for this strategy definition."
        />

        <section className="nas100-candle-stats" aria-label="D1-to-H4 sweep coverage">
          <Statistic title="Accepted D1 sweeps" value={index?.d1SweepCount ?? 0} />
          <Statistic title="Nested H4 activations" value={index?.h4ConfirmedCount ?? 0} />
          <Statistic title="D1 activations without H4" value={index?.h4ExpiredCount ?? 0} />
          <Statistic title="Incomplete source window" value={index?.incompleteWindowCount ?? 0} />
          <Statistic title="Frozen M1 tests" value={breakerComparison?.configurationCount ?? 0} />
          <Statistic title="Positive configurations" value={0} />
        </section>

        {breakerComparison && (
          <section className="nas100-candle-ltf-results" aria-label="M1 breaker and FVG aggregate results">
            <div className="nas100-candle-table-heading">
              <div>
                <Title level={4}>M1 breaker + displacement FVG inside the active H4 candle</Title>
                <Text type="secondary">
                  One frozen entry/stop is tested twice: exact gross 2R and exact gross 2.5R. The two outcomes are never pooled.
                </Text>
              </div>
              <Tag color="red">Candidate none · champion none</Tag>
            </div>
            <Alert
              type="warning"
              showIcon
              title="Gross results are positive, but neither target survives normalized costs"
              description="The intrabar timing correction changes the eligible sample. Both frozen targets have slightly positive gross expectancy, but both become negative under every normalized cost scenario. These costs are hypothetical scenarios rather than broker facts, so neither test is promoted."
            />
            <Table
              className="nas100-candle-table"
              rowKey="configuration"
              columns={breakerSummaryColumns}
              dataSource={breakerSummaries}
              pagination={false}
              size="small"
              scroll={{ x: 1355 }}
            />
          </section>
        )}

        <section className="nas100-candle-filters nas100-candle-filters--daily" aria-label="Filter D1-to-H4 sweeps">
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="Search event, direction or date"
            value={filters.query}
            onChange={(event) => setFilter('query', event.target.value)}
          />
          <Select
            allowClear
            placeholder="All years"
            value={filters.year || undefined}
            onChange={(value) => setFilter('year', value)}
            options={years.map((value) => ({ value, label: String(value) }))}
          />
          <Select
            allowClear
            placeholder="Both directions"
            value={filters.direction || undefined}
            onChange={(value) => setFilter('direction', value)}
            options={['BULLISH', 'BEARISH'].map((value) => ({ value, label: value }))}
          />
          <Select
            allowClear
            placeholder="All H4 stages"
            value={filters.h4Status || undefined}
            onChange={(value) => setFilter('h4Status', value)}
            options={Object.entries(H4_STATUS).map(([value, presentation]) => ({
              value,
              label: presentation.label,
            }))}
          />
          <Select
            allowClear
            placeholder="All M1 setup states"
            value={filters.setupState || undefined}
            onChange={(value) => setFilter('setupState', value)}
            options={[
              { value: 'FILLED', label: 'Filled' },
              { value: 'FORMED_ANY', label: 'Formed · all' },
              { value: 'FORMED_NOT_FILLED', label: 'Formed · not filled' },
              { value: 'NOT_FORMED', label: 'Not formed · 0 / 0' },
            ]}
          />
          <Button onClick={() => setFilters(EMPTY_FILTERS)}>Reset</Button>
        </section>

        {error && (
          <Alert
            type="error"
            showIcon
            title="D1-to-H4 sweep evidence unavailable"
            description={error}
            closable
            onClose={() => setError('')}
          />
        )}

        <div className="nas100-candle-table-heading">
          <div>
            <Title level={4}>Nested D1 and H4 intrabar sweep activations</Title>
            <Text type="secondary">
              Each row has a same-direction H4 activation inside the developing D1 sweep candle and an exact four-hour M1 search boundary.
            </Text>
          </div>
          <Text strong>{visibleSweeps.length} of {sweeps.length} sweeps</Text>
        </div>

        <Spin spinning={loading}>
          <Table
            className="nas100-candle-table"
            columns={columns}
            dataSource={visibleSweeps}
            rowKey="sweepHash"
            pagination={{
              pageSize: 20,
              showSizeChanger: true,
              pageSizeOptions: [20, 50, 100],
              showTotal: (total) => `${total} nested D1/H4 activations`,
            }}
            scroll={{ x: 1380 }}
            locale={{ emptyText: 'No D1-to-H4 sweep matches these filters.' }}
          />
        </Spin>

        <div className="nas100-candle-method">
          <Text strong>Frozen multi-timeframe rule:</Text>
          <Text type="secondary">
            Use the same immediate-candle wick-and-reclaim definition on the developing D1 and H4 candles. Activation is observed at completed M1 closes without waiting for either higher-timeframe close. After H4 activation, require two 2-left/2-right M1 pivots in the matching direction, a strict second-swing close beyond the first wick, a full-wick breaker pivot between them, a completed displacement close through that breaker within five M1 bars, and a same-direction wick-to-wick FVG. Search and trade only inside that H4 candle; test 2R and 2.5R independently.
          </Text>
        </div>
      </div>

      <Modal
        open={Boolean(detail)}
        onCancel={() => setDetail(null)}
        footer={null}
        width={1250}
        title={selectedSummary
          ? `${selectedSummary.eventId} · ${selectedSummary.direction} D1 → H4 → M1 review`
          : 'NAS100 multi-timeframe sweep review'}
        className="nas100-candle-modal"
        styles={{ body: { maxHeight: 'calc(100vh - 150px)', overflowY: 'auto' } }}
        destroyOnHidden
      >
        <Spin spinning={detailLoading}>
          {detail?.summary && (
            <div className="nas100-candle-detail">
              <Alert
                type="info"
                showIcon
                title="How to read the chart"
                description="The D1 and H4 charts show the developing candles at their activation timestamps. Neither activation waits for its higher-timeframe candle to close. The M1 search begins strictly after H4 activation and ends with that same H4 candle."
              />

              <section className="nas100-candle-summary" aria-label="Selected D1-to-H4 sweep summary">
                <div><span>D1 intrabar activation</span><strong>{detail.summary.confirmationTime}</strong></div>
                <div><span>D1 swing bias</span>{directionTag(detail.summary.direction)}</div>
                <div><span>H4 stage</span>{h4StatusTag(detail.summary.h4Status)}</div>
                <div><span>H4 intrabar activation</span><strong>{detail.summary.h4ConfirmationTime || '—'}</strong></div>
                <div><span>Expires</span><strong>{detail.summary.h4WindowExpiry || '—'}</strong></div>
              </section>

              <section className="nas100-candle-checklist" aria-label="Corrected D1 detector checklist">
                <div className="nas100-candle-section-heading">
                  <div>
                    <Title level={4}>Why this daily swing point qualified</Title>
                    <Text type="secondary">Mechanical checks from the single preregistered definition.</Text>
                  </div>
                  <Tag color="green">D1 rule passed</Tag>
                </div>
                <div className="nas100-candle-check-grid">
                  {(detail.checklists?.D1 || []).map((item) => (
                    <div key={item.label}>
                      <CheckCircleOutlined />
                      <span>{item.label}</span>
                      <Tag color="green">{item.status}</Tag>
                      <small>{item.detail}</small>
                    </div>
                  ))}
                </div>
              </section>

              <section className="nas100-candle-checklist" aria-label="H4 confirmation checklist">
                <div className="nas100-candle-section-heading">
                  <div>
                    <Title level={4}>H4 activation inside the developing D1 sweep candle</Title>
                    <Text type="secondary">Same direction, immediate prior H4 candle, evaluated intrabar without waiting for the H4 close.</Text>
                  </div>
                  {h4StatusTag(detail.summary.h4Status)}
                </div>
                <div className="nas100-candle-check-grid">
                  {(detail.checklists?.H4 || []).map((item) => (
                    <div
                      key={item.label}
                      className={`nas100-candle-check--${String(item.status || '').toLowerCase()}`}
                    >
                      <CheckCircleOutlined />
                      <span>{item.label}</span>
                      <Tag color={item.status === 'PASS' ? 'green' : item.status === 'INCOMPLETE' ? 'gold' : 'default'}>
                        {item.status}
                      </Tag>
                      <small>{item.detail}</small>
                    </div>
                  ))}
                </div>
              </section>

              <Descriptions
                bordered
                size="small"
                column={{ xs: 1, sm: 2, md: 4 }}
                items={[
                  { key: 'd1Reference', label: detail.levels?.D1?.referenceLabel || 'D1 C1 reference', children: displayNumber(detail.levels?.D1?.reference) },
                  { key: 'h4Reference', label: detail.levels?.H4?.referenceLabel || 'H4 C1 reference', children: displayNumber(detail.levels?.H4?.reference) },
                  { key: 'latency', label: 'D1-to-H4 activation latency', children: detail.summary.h4LatencyHours === null ? '—' : `${detail.summary.h4LatencyHours} hours` },
                  { key: 'trend', label: 'Trend gate', children: 'None — reversal or continuation' },
                ]}
              />

              <section className="nas100-candle-charts nas100-candle-charts--daily" aria-label="D1 and H4 candle evidence">
                <HistoricalCandleChart
                  timeframe="D1"
                  candles={detail.m1WindowReview?.d1ContextCandles || detail.candles?.D1 || []}
                  decisionTime={detail.summary.candle2Start}
                  decisionLabel="Candle 2"
                  referenceLevel={detail.levels?.D1?.reference}
                  referenceLabel={detail.levels?.D1?.referenceLabel}
                  eligibleWindowLabel="D1 sweep candle"
                />
                <HistoricalCandleChart
                  timeframe="H4"
                  candles={detail.candles?.H4 || []}
                  decisionTime={(detail.candles?.H4 || []).find((candle) => candle.role === 'CANDLE_2')?.timestamp || null}
                  decisionLabel="H4 Candle 2"
                  referenceLevel={detail.levels?.H4?.reference}
                  referenceLabel={detail.levels?.H4?.referenceLabel || 'H4 reference'}
                  eligibleWindowLabel="Active D1 window"
                />
              </section>

              {detail.breakerFvg && (
                <section className="nas100-candle-ltf-detail" aria-label="Selected M1 breaker and FVG comparison">
                  <div className="nas100-candle-section-heading">
                    <div>
                      <Title level={4}>M1 breaker entries inside this H4 candle only</Title>
                      <Text type="secondary">
                        Both rows use the same first frozen M1 candidate, entry, and stop. Only the 2R versus 2.5R target changes.
                      </Text>
                    </div>
                    <Tag color="red">No promoted strategy</Tag>
                  </div>
                  <Table
                    className="nas100-candle-table"
                    rowKey="configuration"
                    columns={breakerDetailColumns}
                    dataSource={detail.breakerFvg.configurations || []}
                    pagination={false}
                    size="small"
                    scroll={{ x: 1110 }}
                  />

                  {selectedBreaker && (
                    <div className="nas100-candle-ltf-chart">
                      <Descriptions
                        bordered
                        size="small"
                        column={{ xs: 1, sm: 2, md: 4 }}
                        items={[
                          { key: 'test', label: 'Selected test', children: BREAKER_FVG_LABELS[selectedBreaker.configuration] || selectedBreaker.configuration },
                          { key: 'available', label: 'Setup available', children: selectedBreaker.candidateAvailableAt || '—' },
                          { key: 'fill', label: 'Proven fill', children: selectedBreaker.entryBarStart || '—' },
                          { key: 'outcome', label: 'Outcome', children: ltfOutcomeTag(selectedBreaker.outcome) },
                          { key: 'entry', label: 'Breaker proximal-edge entry', children: displayNumber(selectedBreaker.entryReference) },
                          { key: 'stop', label: 'Beyond distal breaker wick', children: displayNumber(selectedBreaker.stopReference) },
                          { key: 'target', label: `Exact gross ${displayNumber(selectedBreaker.targetMultiple)}R target`, children: displayNumber(selectedBreaker.targetReference) },
                          { key: 'cost', label: 'Normalized medium-cost result', children: signedR(selectedBreaker.normalizedMediumCostNetR) },
                        ]}
                      />
                      <HistoricalCandleChart
                        timeframe={`${selectedBreaker.timeframe} · ${BREAKER_FVG_LABELS[selectedBreaker.configuration] || selectedBreaker.configuration}`}
                        candles={selectedBreakerDisplayCandles}
                        levels={{
                          zones: selectedBreaker.zones,
                          entry: selectedBreaker.entryReference,
                          stop: selectedBreaker.stopReference,
                          target: selectedBreaker.targetReference,
                        }}
                        decisionTime={selectedBreaker.candidateAvailableAt}
                        decisionLabel="setup available"
                        eligibleWindowLabel="Owning H4 window"
                      />
                    </div>
                  )}

                  {noBreakerFilled && detail.m1WindowReview?.candles?.length > 0 && (
                    <div className="nas100-candle-ltf-chart nas100-candle-window-review">
                      <div className="nas100-candle-section-heading">
                        <div>
                          <Title level={4}>M1 chart for the complete H4 window</Title>
                          <Text type="secondary">
                            This is the raw M1 shape behind the zero-filled result.
                          </Text>
                        </div>
                        <Tag>Chart only</Tag>
                      </div>
                      <Alert
                        type="info"
                        showIcon
                        title={noBreakerFormed ? 'No breaker + FVG formed' : 'A setup formed, but price did not fill it'}
                        description="The full owning H4 interval is shown for visual review only. No new entry, stop, target, fill, outcome, or execution is created from this chart."
                      />
                      <HistoricalCandleChart
                        timeframe="M1 · complete H4 interval · no setup"
                        candles={detail.m1WindowReview.candles}
                        decisionTime={detail.m1WindowReview.h4ActivationTime}
                        decisionLabel="H4 sweep active"
                        eligibleWindowLabel="Owning H4 window"
                      />
                    </div>
                  )}
                </section>
              )}

              <Alert
                type="warning"
                showIcon
                title="What this result does not mean"
                description={[
                  ...(detail.limitations || []).filter((limitation) => (
                    !detail.breakerFvg
                    || !String(limitation).includes('no lower-timeframe entry')
                  )),
                  ...(detail.breakerFvg?.limitations || []),
                ].join(' ')}
              />
            </div>
          )}
        </Spin>
      </Modal>
    </Sidebar>
  );
};

export default Nas100Candle;

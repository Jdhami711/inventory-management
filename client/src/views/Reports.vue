<template>
  <div class="reports">
    <div class="page-header">
      <h2>{{ t('reports.title') }}</h2>
      <p>{{ t('reports.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="!hasData" class="card empty-state">{{ t('reports.noData') }}</div>
    <div v-else>
      <!-- Quarterly Performance -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.quarterly.title') }}</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('reports.quarterly.quarter') }}</th>
                <th>{{ t('reports.quarterly.totalOrders') }}</th>
                <th>{{ t('reports.quarterly.totalRevenue') }}</th>
                <th>{{ t('reports.quarterly.avgOrderValue') }}</th>
                <th>{{ t('reports.quarterly.fulfillmentRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in quarterlyData" :key="q.quarter">
                <td><strong>{{ q.quarter }}</strong></td>
                <td>{{ q.total_orders }}</td>
                <td>{{ formatMoney(q.total_revenue) }}</td>
                <td>{{ formatMoney(q.avg_order_value) }}</td>
                <td>
                  <span :class="['badge', getFulfillmentClass(q.fulfillment_rate)]">
                    {{ q.fulfillment_rate }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Trends Chart -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.monthlyTrend.title') }}</h3>
        </div>
        <div class="chart-container">
          <div class="bar-chart">
            <div v-for="row in monthRows" :key="row.month" class="bar-wrapper">
              <div class="bar-container">
                <div
                  class="bar"
                  role="img"
                  :aria-label="row.barTitle"
                  :style="{ height: row.barHeight + 'px' }"
                  :title="row.barTitle"
                ></div>
              </div>
              <div class="bar-label">{{ row.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Month-over-Month Comparison -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('reports.momAnalysis.title') }}</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('reports.momAnalysis.month') }}</th>
                <th>{{ t('reports.momAnalysis.orders') }}</th>
                <th>{{ t('reports.momAnalysis.revenue') }}</th>
                <th>{{ t('reports.momAnalysis.change') }}</th>
                <th>{{ t('reports.momAnalysis.growthRate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in monthRows" :key="row.month">
                <td><strong>{{ row.label }}</strong></td>
                <td>{{ row.order_count }}</td>
                <td>{{ formatMoney(row.revenue) }}</td>
                <td>
                  <span v-if="row.change !== null" :class="row.changeClass">{{ row.change }}</span>
                  <span v-else>-</span>
                </td>
                <td>
                  <span v-if="row.growthRate !== null" :class="row.changeClass">{{ row.growthRate }}</span>
                  <span v-else>-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.totalRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(totalRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.avgMonthlyRevenue') }}</div>
          <div class="stat-value">{{ formatMoney(avgMonthlyRevenue) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.totalOrders') }}</div>
          <div class="stat-value">{{ formatCount(totalOrders) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('reports.summary.bestQuarter') }}</div>
          <div class="stat-value">{{ bestQuarter }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrencyWithDecimals } from '../utils/currency'

// Height in px of the tallest bar; must match .bar-container in the styles
const MAX_BAR_HEIGHT = 200

export default {
  name: 'Reports',
  setup() {
    const { t, currentLocale, currentCurrency } = useI18n()
    const {
      selectedPeriod,
      selectedLocation,
      selectedCategory,
      selectedStatus,
      getCurrentFilters
    } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const quarterlyData = ref([])
    const monthlyData = ref([])

    // Filters can change faster than the API answers, so each load gets an id and only
    // the latest one may write state; otherwise a slow earlier response could overwrite
    // newer data (or clear the loading flag while a newer request is still running).
    let latestRequestId = 0

    const loadData = async () => {
      const requestId = ++latestRequestId
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        // Independent requests, so fetch them in parallel
        const [quarterly, monthly] = await Promise.all([
          api.getQuarterlyReports(filters),
          api.getMonthlyTrends(filters)
        ])
        if (requestId !== latestRequestId) return
        quarterlyData.value = quarterly
        monthlyData.value = monthly
      } catch (err) {
        if (requestId !== latestRequestId) return
        error.value = t('reports.loadError') + ': ' + err.message
        console.error('Error loading reports:', err)
      } finally {
        if (requestId === latestRequestId) loading.value = false
      }
    }

    // Amounts are stored in USD; formatCurrency converts for display when JPY is active
    const formatMoney = (amount) => formatCurrencyWithDecimals(amount, currentCurrency.value, 2)

    // Counts follow the app language, not the browser's default locale
    const formatCount = (count) => count.toLocaleString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US')

    // Turn "YYYY-MM" into a locale-aware label ("Jan 2025" / "2025年1月").
    // The date is built and formatted in UTC so the timezone cannot shift the month.
    const formatMonth = (monthStr) => {
      const [year, month] = String(monthStr).split('-').map(Number)
      if (!year || !month || month < 1 || month > 12) return String(monthStr)
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Intl.DateTimeFormat(locale, { year: 'numeric', month: 'short', timeZone: 'UTC' })
        .format(new Date(Date.UTC(year, month - 1, 1)))
    }

    const getFulfillmentClass = (rate) => {
      if (rate >= 90) return 'success'
      if (rate >= 75) return 'warning'
      return 'danger'
    }

    const hasData = computed(() => monthlyData.value.length > 0 || quarterlyData.value.length > 0)

    // Bars are scaled against the tallest month, computed once rather than per bar
    const maxRevenue = computed(() => {
      return monthlyData.value.reduce((max, m) => Math.max(max, m.revenue), 0)
    })

    // One row per month with everything the chart and the month-over-month table need.
    // Change/growth compare against the previous entry in the (sorted) list; the first
    // month has nothing to compare to so those fields are null.
    const monthRows = computed(() => {
      return monthlyData.value.map((m, i) => {
        const label = formatMonth(m.month)
        const row = {
          ...m,
          label,
          barHeight: maxRevenue.value > 0 ? (m.revenue / maxRevenue.value) * MAX_BAR_HEIGHT : 0,
          barTitle: t('reports.monthlyTrend.barTitle', {
            month: label,
            revenue: formatMoney(m.revenue),
            count: m.order_count
          }),
          change: null,
          growthRate: null,
          changeClass: ''
        }

        if (i > 0) {
          const previous = monthlyData.value[i - 1].revenue
          const diff = m.revenue - previous
          const sign = diff > 0 ? '+' : diff < 0 ? '-' : ''
          row.change = sign + formatMoney(Math.abs(diff))
          row.changeClass = diff > 0 ? 'positive-change' : diff < 0 ? 'negative-change' : ''
          // A zero previous month has no meaningful percentage
          row.growthRate = previous === 0
            ? t('reports.momAnalysis.notAvailable')
            : (diff > 0 ? '+' : '') + ((diff / previous) * 100).toFixed(1) + '%'
        }
        return row
      })
    })

    const totalRevenue = computed(() => monthlyData.value.reduce((sum, m) => sum + m.revenue, 0))
    const totalOrders = computed(() => monthlyData.value.reduce((sum, m) => sum + m.order_count, 0))
    const avgMonthlyRevenue = computed(() => {
      return monthlyData.value.length > 0 ? totalRevenue.value / monthlyData.value.length : 0
    })
    const bestQuarter = computed(() => {
      const best = quarterlyData.value.reduce(
        (top, q) => (top === null || q.total_revenue > top.total_revenue ? q : top),
        null
      )
      return best ? best.quarter : '-'
    })

    // Reports respect the same global filter bar as the other pages
    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], () => {
      loadData()
    })

    onMounted(() => {
      loadData()
    })

    return {
      t,
      loading,
      error,
      quarterlyData,
      hasData,
      monthRows,
      totalRevenue,
      totalOrders,
      avgMonthlyRevenue,
      bestQuarter,
      formatMoney,
      formatCount,
      getFulfillmentClass
    }
  }
}
</script>

<style scoped>
/* Cards, tables, badges, stat cards, loading and error states come from the global
   styles in App.vue; only report-specific styling lives here. */
.empty-state {
  text-align: center;
  color: #64748b;
  padding: 2rem 1.5rem;
}

.chart-container {
  padding: 2rem 1rem;
  min-height: 300px;
}

.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  height: 250px;
  gap: 0.5rem;
}

.bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  max-width: 80px;
}

.bar-container {
  height: 200px;
  display: flex;
  align-items: flex-end;
  width: 100%;
}

.bar {
  width: 100%;
  background: linear-gradient(to top, #3b82f6, #60a5fa);
  border-radius: 4px 4px 0 0;
  transition: all 0.3s;
  cursor: pointer;
}

.bar:hover {
  background: linear-gradient(to top, #2563eb, #3b82f6);
}

.bar-label {
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  transform: rotate(-45deg);
  white-space: nowrap;
  margin-top: 1.5rem;
}

.positive-change {
  color: #16a34a;
  font-weight: 600;
}

.negative-change {
  color: #dc2626;
  font-weight: 600;
}
</style>

<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="loadError" class="error">{{ loadError }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-header">
          <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
          <span class="budget-value" aria-live="polite">{{ formatMoney(budget) }}</span>
        </div>
        <input
          id="budget-slider"
          class="budget-slider"
          type="range"
          min="0"
          :max="sliderMax"
          :step="SLIDER_STEP"
          :value="budget"
          :style="{ '--fill': fillPercent + '%' }"
          :aria-valuetext="formatMoney(budget)"
          @input="onBudgetInput"
        />
        <div class="budget-scale">
          <span>{{ formatMoney(0) }}</span>
          <span>{{ formatMoney(sliderMax) }}</span>
        </div>
        <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ formatMoney(budget) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.plannedSpend') }}</div>
          <div class="stat-value">{{ formatMoney(plan.total_cost, 2) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatMoney(plan.remaining, 2) }}</div>
        </div>
      </div>

      <div v-if="orderResult" class="banner banner-success" role="status">
        <span>{{ t('restocking.orderPlaced', { orderNumber: orderResult.order_number, days: orderResult.lead_time_days }) }}</span>
        <router-link to="/orders" class="banner-link">{{ t('restocking.viewOrders') }}</router-link>
      </div>
      <div v-if="orderError" class="banner banner-error" role="alert">{{ orderError }}</div>
      <div v-if="alreadyOrderedSkus.length > 0" class="banner banner-warning" role="alert">
        <span>{{ t('restocking.duplicateWarning', { skus: alreadyOrderedSkus.join(', ') }) }}</span>
        <router-link to="/orders" class="banner-link">{{ t('restocking.viewOrders') }}</router-link>
      </div>

      <div class="card">
        <div class="card-header table-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }} ({{ plan.items.length }})</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="plan.items.length === 0 || submitting || refreshing"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="plan.items.length === 0" class="empty-state">{{ t('restocking.empty') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineCost') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in plan.items" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>
                  <span :class="['badge', item.trend]">{{ t('trends.' + item.trend) }}</span>
                </td>
                <td class="num">{{ item.quantity.toLocaleString() }}</td>
                <td class="num">{{ formatMoney(item.unit_cost, 2) }}</td>
                <td class="num"><strong>{{ formatMoney(item.line_cost, 2) }}</strong></td>
                <td class="num">{{ t('restocking.leadTimeUnit', { count: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

const SLIDER_STEP = 50
const DEBOUNCE_MS = 250
const DEFAULT_BUDGET = 1000

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const loadError = ref(null)
    const refreshing = ref(false)
    const submitting = ref(false)
    const orderResult = ref(null)
    const orderError = ref(null)

    // The budget is always held in USD; only the display is converted to the active currency
    const budget = ref(0)
    const sliderMax = ref(SLIDER_STEP)
    const plan = ref({ total_cost: 0, remaining: 0, items: [] })

    const formatMoney = (amount, decimals = 0) => {
      return decimals > 0
        ? formatCurrencyWithDecimals(amount, currentCurrency.value, decimals)
        : formatCurrency(amount, currentCurrency.value)
    }

    // SKUs that already appear on a submitted restock order. Recommendations are
    // computed from the forecast alone and do not subtract pending orders, so this
    // is only used to warn the user; it never changes the plan or blocks ordering.
    const submittedSkus = ref(new Set())

    const loadSubmittedSkus = async () => {
      try {
        const orders = await api.getRestockOrders()
        submittedSkus.value = new Set(orders.flatMap(order => order.items.map(item => item.sku)))
      } catch (err) {
        // The warning is best-effort: failing to load it must not break restocking
        console.error('Failed to load submitted restock orders:', err)
      }
    }

    const alreadyOrderedSkus = computed(() => {
      return plan.value.items
        .map(item => item.sku)
        .filter(sku => submittedSkus.value.has(sku))
    })

    // Drives the filled portion of the slider track (see --fill in the styles)
    const fillPercent = computed(() => {
      return sliderMax.value > 0 ? (budget.value / sliderMax.value) * 100 : 0
    })

    // Responses can arrive out of order while the user drags the slider, so each
    // request gets an id and only the latest one is allowed to update the plan.
    let latestRequestId = 0
    let debounceTimer = null

    const fetchPlan = async (amount) => {
      const requestId = ++latestRequestId
      refreshing.value = true
      try {
        const result = await api.getRestockRecommendations(amount)
        if (requestId !== latestRequestId) return null
        plan.value = result
        loadError.value = null
        return result
      } catch (err) {
        if (requestId === latestRequestId) {
          loadError.value = t('restocking.loadError') + ': ' + err.message
        }
        return null
      } finally {
        if (requestId === latestRequestId) refreshing.value = false
      }
    }

    const onBudgetInput = (event) => {
      budget.value = Number(event.target.value)
      // A previous confirmation no longer describes the plan that is on screen
      orderResult.value = null
      orderError.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => fetchPlan(budget.value), DEBOUNCE_MS)
    }

    const placeOrder = async () => {
      // Guard against double submits (the button is also disabled while submitting)
      if (submitting.value || plan.value.items.length === 0) return
      // Make sure a pending debounced fetch cannot replace the plan we are ordering
      clearTimeout(debounceTimer)
      submitting.value = true
      orderError.value = null
      try {
        orderResult.value = await api.createRestockOrder(plan.value.items)
        // Refresh so the duplicate warning immediately covers the order just placed
        await Promise.all([fetchPlan(budget.value), loadSubmittedSkus()])
      } catch (err) {
        orderError.value = t('restocking.orderError')
      } finally {
        submitting.value = false
      }
    }

    onMounted(async () => {
      // A zero-budget request is a cheap way to learn the cost of restocking everything,
      // which becomes the slider's upper bound.
      loadSubmittedSkus()
      const initial = await fetchPlan(0)
      if (initial) {
        // Round up to the next step so the slider can reach the full-restock point
        sliderMax.value = Math.max(SLIDER_STEP, Math.ceil(initial.total_needed_cost / SLIDER_STEP) * SLIDER_STEP)
        budget.value = Math.min(DEFAULT_BUDGET, sliderMax.value)
        await fetchPlan(budget.value)
      }
      loading.value = false
    })

    onBeforeUnmount(() => {
      clearTimeout(debounceTimer)
      // Invalidate in-flight requests so they do not touch state after unmount
      latestRequestId++
    })

    return {
      t,
      translateProductName,
      loading,
      loadError,
      refreshing,
      submitting,
      orderResult,
      orderError,
      budget,
      sliderMax,
      plan,
      alreadyOrderedSkus,
      fillPercent,
      formatMoney,
      onBudgetInput,
      placeOrder,
      SLIDER_STEP
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

/* Slider: --fill is set inline and paints the portion of the track left of the thumb */
.budget-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: linear-gradient(to right, #2563eb 0%, #2563eb var(--fill, 0%), #e2e8f0 var(--fill, 0%), #e2e8f0 100%);
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #ffffff;
  border: 3px solid #2563eb;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.25);
  transition: transform 0.15s ease;
}

.budget-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.budget-slider::-moz-range-track {
  height: 8px;
  border-radius: 999px;
  background: #e2e8f0;
}

.budget-slider::-moz-range-progress {
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
}

.budget-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #ffffff;
  border: 3px solid #2563eb;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.25);
}

.budget-slider:focus-visible {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.3);
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.813rem;
  color: #64748b;
}

.budget-hint {
  margin-top: 0.75rem;
  font-size: 0.813rem;
  color: #64748b;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.place-order-btn {
  background: #2563eb;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  padding: 0.625rem 1.25rem;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.num {
  text-align: right;
}

.empty-state {
  padding: 2rem 1.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.875rem 1.25rem;
  margin-bottom: 1.5rem;
  border-radius: 8px;
  font-size: 0.938rem;
  font-weight: 500;
}

.banner-success {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
}

.banner-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.banner-warning {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.banner-link {
  color: #2563eb;
  font-weight: 600;
  text-decoration: none;
}

.banner-link:hover {
  text-decoration: underline;
}

@media (max-width: 768px) {
  .budget-value {
    font-size: 1.5rem;
  }

  .table-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

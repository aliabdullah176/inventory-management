<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetLabel') }}</h3>
        </div>
        <div class="budget-body">
          <div class="budget-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
          <div class="budget-slider">
            <input
              type="range"
              class="slider"
              :min="0"
              :max="maxBudget"
              :step="budgetStep"
              v-model.number="budget"
            />
            <div class="slider-labels">
              <span>{{ currencySymbol }}0</span>
              <span>{{ currencySymbol }}{{ maxBudget.toLocaleString() }}</span>
            </div>
          </div>
          <p class="budget-hint">{{ t('restocking.budgetHint') }}</p>
          <p class="budget-full-cost">
            {{ t('restocking.fullRestockCost') }}: <strong>{{ currencySymbol }}{{ maxBudget.toLocaleString() }}</strong>
          </p>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.summary.items') }}</div>
          <div class="stat-value">{{ recommended.length }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.summary.totalCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ totalCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.summary.remaining') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ remaining.toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommended') }}</h3>
        </div>

        <div v-if="recommended.length === 0" class="empty-state">
          {{ t('restocking.noRecommendations') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.currentStock') }}</th>
                <th>{{ t('restocking.table.recommendedQty') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineTotal') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommended" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ item.name }}</td>
                <td>
                  <span :class="['badge', item.trend]">
                    {{ t(`trends.${item.trend}`) }}
                  </span>
                </td>
                <td>{{ item.currentStock }}</td>
                <td><strong>{{ item.quantity }}</strong></td>
                <td>{{ currencySymbol }}{{ item.unitCost.toFixed(2) }}</td>
                <td><strong>{{ currencySymbol }}{{ item.lineCost.toLocaleString() }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="successMessage" class="success-banner">
          {{ successMessage }}
        </div>

        <div class="place-order-row">
          <button
            class="po-button create"
            :disabled="recommended.length === 0 || placing"
            @click="placeOrder"
          >
            {{ placing ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()
    const router = useRouter()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const { selectedLocation, selectedCategory, getCurrentFilters } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const inventory = ref([])
    const budget = ref(0)
    const placing = ref(false)
    const successMessage = ref('')

    // Build candidate restock lines from forecasts joined to inventory
    const candidates = computed(() => {
      const inventoryBySku = new Map(inventory.value.map(item => [item.sku, item]))

      const lines = []
      for (const forecast of forecasts.value) {
        const inv = inventoryBySku.get(forecast.item_sku)
        if (!inv) continue

        const gap = forecast.forecasted_demand - forecast.current_demand
        if (gap <= 0) continue

        lines.push({
          sku: forecast.item_sku,
          name: forecast.item_name,
          trend: forecast.trend,
          quantity: gap,
          currentStock: inv.quantity_on_hand,
          unitCost: inv.unit_cost,
          lineCost: inv.unit_cost * gap
        })
      }

      // Increasing-trend items first, then by gap size descending
      return lines.sort((a, b) => {
        const aIncreasing = a.trend === 'increasing' ? 0 : 1
        const bIncreasing = b.trend === 'increasing' ? 0 : 1
        if (aIncreasing !== bIncreasing) return aIncreasing - bIncreasing
        return b.quantity - a.quantity
      })
    })

    const maxBudget = computed(() => {
      const totalCost = candidates.value.reduce((sum, item) => sum + item.lineCost, 0)
      if (totalCost <= 0) return 1000
      return Math.ceil(totalCost / 1000) * 1000
    })

    const budgetStep = computed(() => {
      return Math.max(50, Math.round((maxBudget.value / 100) / 50) * 50)
    })

    const recommended = computed(() => {
      let running = 0
      const lines = []
      for (const item of candidates.value) {
        if (running + item.lineCost <= budget.value) {
          lines.push(item)
          running += item.lineCost
        }
      }
      return lines
    })

    const totalCost = computed(() => {
      return recommended.value.reduce((sum, item) => sum + item.lineCost, 0)
    })

    const remaining = computed(() => {
      return budget.value - totalCost.value
    })

    const setDefaultBudget = () => {
      const half = maxBudget.value / 2
      const step = budgetStep.value
      let defaultBudget = Math.round(half / step) * step
      if (defaultBudget > maxBudget.value) defaultBudget = maxBudget.value
      budget.value = defaultBudget
    }

    const loadData = async () => {
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()

        const [forecastsData, inventoryData] = await Promise.all([
          api.getDemandForecasts(),
          api.getInventory({
            warehouse: filters.warehouse,
            category: filters.category
          })
        ])

        forecasts.value = forecastsData
        inventory.value = inventoryData

        setDefaultBudget()
      } catch (err) {
        error.value = 'Failed to load restocking data: ' + err.message
      } finally {
        loading.value = false
      }
    }

    watch([selectedLocation, selectedCategory], () => {
      loadData()
    })

    const placeOrder = async () => {
      try {
        placing.value = true
        error.value = null

        const order = await api.createOrder({
          items: recommended.value.map(item => ({
            sku: item.sku,
            name: item.name,
            quantity: item.quantity,
            unit_price: item.unitCost
          })),
          warehouse: selectedLocation.value !== 'all' ? selectedLocation.value : null
        })

        successMessage.value = t('restocking.successMessage', { orderNumber: order.order_number })
        router.push('/orders')
      } catch (err) {
        error.value = 'Failed to place order: ' + err.message
      } finally {
        placing.value = false
      }
    }

    onMounted(loadData)

    return {
      t,
      currencySymbol,
      loading,
      error,
      forecasts,
      inventory,
      budget,
      placing,
      successMessage,
      candidates,
      maxBudget,
      budgetStep,
      recommended,
      totalCost,
      remaining,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-body {
  padding: 1.5rem;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 1.25rem;
}

.budget-slider {
  margin-bottom: 0.75rem;
}

.slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: background 0.2s;
}

.slider::-webkit-slider-thumb:hover {
  background: #3b82f6;
}

.slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  transition: background 0.2s;
}

.slider::-moz-range-thumb:hover {
  background: #3b82f6;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.813rem;
  color: #64748b;
  margin-top: 0.5rem;
}

.budget-hint {
  color: #64748b;
  font-size: 0.875rem;
  margin: 0.75rem 0 0.25rem;
}

.budget-full-cost {
  color: #64748b;
  font-size: 0.875rem;
  margin: 0.25rem 0 0;
}

.budget-full-cost strong {
  color: #0f172a;
}

.empty-state {
  padding: 2.5rem 1.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.9rem;
}

.success-banner {
  margin: 0 1.5rem 1rem;
  padding: 0.875rem 1rem;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 8px;
  color: #059669;
  font-size: 0.875rem;
  font-weight: 500;
}

.place-order-row {
  display: flex;
  justify-content: flex-end;
  padding: 1rem 1.5rem 1.5rem;
}

.po-button {
  padding: 0.625rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.po-button.create {
  background: #3b82f6;
  color: white;
}

.po-button.create:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.po-button:disabled {
  background: #cbd5e1;
  color: #94a3b8;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.error {
  color: #ef4444;
}
</style>

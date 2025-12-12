<script lang="ts" setup>
import { ref, computed, watch } from 'vue'
import type { Option } from '../boardGame.mts'

interface Props {
  name: string
  options: Option[]
  placeholder: string
  disabled: boolean
  maxItems: number
}

const props = defineProps<Props>()
const name = ref(props.name)
const options = ref(props.options)
const placeholder = ref(props.placeholder)
const disabled = ref(props.disabled)
const searchFilter = ref('')
const selected = ref<Option | undefined>(undefined)
const optionsShown = ref(false)

const emit = defineEmits(['selected', 'filter', 'active'])

const filteredOptions = computed(() => {
  const filter = searchFilter.value.toLowerCase()

  return options.value
    .filter(
      (option) =>
        !filter ||
        option.name?.toLowerCase().includes(filter) ||
        option.id?.toLowerCase().includes(filter),
    )
    .slice(0, props.maxItems)
})

watch(searchFilter, () => {
  const filter = searchFilter.value?.trim() ?? ''
  if (!filter) {
    // No free text typed – do not preselect anything
    selected.value = undefined
  } else if (filteredOptions.value.length === 0) {
    selected.value = undefined
  } else {
    selected.value = filteredOptions.value[0]
  }
  // always emit on input change so outer components can refetch options
  emit('filter', searchFilter.value)
  // Also emit current active selection candidate (or undefined)
  emit('active', selected.value)
})

const showOptions = () => {
  optionsShown.value = true
  searchFilter.value = ''
}

const exit = () => {
  if (!selected.value) {
    selected.value = undefined
    searchFilter.value = ''
  } else {
    searchFilter.value = selected.value.name
  }
  emit('selected', selected.value)
  optionsShown.value = false
}

const selectOption = (option: Option) => {
  selected.value = option
  optionsShown.value = false
  searchFilter.value = selected.value.name
  emit('selected', selected.value)
}

const keyMonitor = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && filteredOptions.value[0]) {
    selectOption(filteredOptions.value[0])
  }
}

defineExpose({
  searchFilter,
})
</script>

<template>
  <div class="dropdown" v-if="options">
    <!-- Dropdown Input -->
    <input
      class="dropdown-input"
      :name="name"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      @focus="showOptions()"
      @blur="exit()"
      @keyup="keyMonitor"
      v-model="searchFilter"
      :disabled="disabled"
      :placeholder="placeholder"
    />

    <!-- Dropdown Menu -->
    <div class="dropdown-content card" v-show="optionsShown">
      <div
        class="dropdown-item"
        @mousedown="selectOption(option)"
        v-for="(option, index) in filteredOptions"
        :key="index"
      >
        {{ option.name || option.id || '-' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.dropdown {
  position: relative;
  display: inline-block;
  width: 100%;
  border-radius: var(--radius-md);
}

.dropdown-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  box-sizing: border-box;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text);
  border: none;
  outline: none;
  font-size: var(--text-md);
  caret-color: var(--color-text);
  appearance: none;
  -webkit-appearance: none;
}

.dropdown-input:focus,
.dropdown-input:focus-visible {
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  background: transparent;
}

.dropdown-content {
  position: absolute;
  background: var(--color-surface);
  min-width: 100%;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-2);
  z-index: 10;
}

.dropdown-item {
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
}

.dropdown-item:hover {
  background: var(--color-surface-2);
}
</style>

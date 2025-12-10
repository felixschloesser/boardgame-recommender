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

const emit = defineEmits(['selected', 'filter'])

const filteredOptions = computed(() => {
  const filtered = []
  const regOption = new RegExp(searchFilter.value, 'ig')
  for (const option of options.value) {
    if (searchFilter.value.length < 1 || option.name.match(regOption)) {
      if (filtered.length < props.maxItems) {
        filtered.push(option)
      }
    }
  }
  if (!searchFilter.value) {
    return options.value.slice(0, props.maxItems)
  }
  return options.value
    .filter(
      (option) =>
        (option.name && option.name.toLowerCase().includes(searchFilter.value.toLowerCase())) ||
        (option.id && option.id.toLowerCase().includes(searchFilter.value.toLowerCase())),
    )
    .slice(0, props.maxItems)
})

watch(searchFilter, () => {
  if (filteredOptions.value.length === 0) {
    selected.value = undefined
  } else {
    selected.value = filteredOptions.value[0]
    emit('filter', searchFilter.value)
  }
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
</script>

<template>
  <div class="dropdown" v-if="options">
    <!-- Dropdown Input -->
    <input
      class="dropdown-input"
      :name="name"
      @focus="showOptions()"
      @blur="exit()"
      @keyup="keyMonitor"
      v-model="searchFilter"
      :disabled="disabled"
      :placeholder="placeholder"
    />

    <!-- Dropdown Menu -->
    <div class="dropdown-content" v-show="optionsShown">
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
}

.dropdown-input {
  width: 100%;
  padding: 8px;
  box-sizing: border-box;
}

.dropdown-content {
  position: absolute;
  background-color: #f9f9f9;
  min-width: 100%;
  max-height: 200px;
  overflow-y: auto;
  box-shadow: 0px 8px 16px 0px rgba(0, 0, 0, 0.2);
  z-index: 1;
}
</style>

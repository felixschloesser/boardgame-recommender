<script lang="ts" setup>
import DropDownSearch from './DropDownSearch.vue'
import type { Option } from '../boardGame.mjs'
import { ref, computed } from 'vue'
import * as api from '@/api.mjs'
import type BoardGame from '../boardGame.mjs'

interface Props {
  options: Option[]
}

const props = defineProps<Props>()
const selectedGame = ref<Option | undefined>(undefined)
const activeOption = ref<Option | undefined>(undefined)
const options = ref<Option[]>(props.options)

const emit = defineEmits(['addGame', 'removeGame'])
const searchBar = ref<InstanceType<typeof DropDownSearch>>()
const addedGames = ref<Option[]>([])

const addGame = () => {
  // Prefer an explicitly selected game; otherwise fall back to the active option from the typeahead
  const toAdd = selectedGame.value ?? activeOption.value
  if (toAdd) {
    // Avoid adding duplicates
    if (!addedGames.value.find((game) => game.id === toAdd.id)) {
      addedGames.value.push(toAdd)
      if (searchBar.value) {
        searchBar.value.searchFilter = '' // Clear search input
      }
      emit('addGame', toAdd)
    }
    selectedGame.value = undefined
    activeOption.value = undefined
  }
}

const removeGame = (game: Option) => {
  addedGames.value = addedGames.value.filter((g) => g.id !== game.id)
  emit('removeGame', game)
}

const refetchOptions = async (filter: string) => {
  options.value.splice(0, options.value.length) // Clear current options
  const newGames: BoardGame[] = await api.getGames(filter)
  const newOptions = newGames.map((game) => ({
    id: game.id,
    name: game.title,
  }))
  options.value.push(...newOptions)
}

defineExpose({
  addedGames,
})

// Auto-add when a selection comes from the dropdown
const onSelected = (option?: Option) => {
  if (!option) return
  selectedGame.value = option
  addGame()
}

// just clear the search filter on exit
const onExit = () => {
  if (searchBar.value) {
    searchBar.value.searchFilter = ''
  }
}

// Track the currently active option while typing (top match from dropdown)
const onActive = (option?: Option) => {
  activeOption.value = option
}

const canAdd = computed(() => {
  const candidate = selectedGame.value ?? activeOption.value
  if (!candidate) return false
  return !addedGames.value.some((g) => g.id === candidate.id)
})
</script>

<template>
  <div>
    <div class="inputgames card">
      <DropDownSearch
        ref="searchBar"
        name="liked-games"
        :options="options"
        placeholder="Search for a game..."
        :disabled="false"
        :maxItems="5"
        @selected="onSelected"
        @active="onActive"
        @exit="onExit"
        @filter="(filter) => refetchOptions(filter)"
      />
      <button class="add-btn btn-primary" @click="addGame" :disabled="!canAdd" title="Add game">
        +
      </button>
    </div>
    <div class="addedgames">
      <div class="game" v-for="game in addedGames" :key="game.id">
        <div class="game-name">{{ game.name }}</div>
        <button class="remove-btn btn-outline" @click="removeGame(game)" title="Remove">
          <Icon icon="material-symbols:close-rounded" width="18" height="18" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.inputgames {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  justify-content: center;
  margin: 0 auto;
  padding: var(--space-3);
  max-width: 520px;
}

.inputgames:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-2);
}

.add-btn {
  font-weight: 700;
  cursor: pointer;
  font-size: 20px;
  border-radius: var(--radius-sm);
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.addedgames {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
}

.game {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: var(--radius-md);
  width: 100%;
  max-width: 520px;
}

.game-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1 1 auto;
}

.remove-btn {
  width: 32px;
  height: 32px;
  cursor: pointer;
  padding: 6px 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>

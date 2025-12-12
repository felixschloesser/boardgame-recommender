
<script lang="ts" setup>
import { computed, ref } from 'vue'
import type { Recommendation } from '../recommendation.mjs'
import { addRecommendationToWishlist, inWishlist, removeRecommendationFromWishlist } from '../wishlist.mjs'

interface Props {
  recommendation: Recommendation
  explanationStyle: 'references' | 'features'
  size: 'small' | 'large'
}

const emit = defineEmits(['viewgame'])
const props = defineProps<Props>()

const isInWishlist = ref(inWishlist(props.recommendation))

const toggleWishList = () => {
  if (inWishlist(props.recommendation)) {
    removeRecommendationFromWishlist(props.recommendation)
    isInWishlist.value = false
  } else {
    isInWishlist.value = true
    addRecommendationToWishlist(props.recommendation)
  }
}

// Normalize influence to 'positive' | 'neutral' | 'negative'
const normInfluence = (val: unknown): 'positive' | 'neutral' | 'negative' => {
  if (typeof val === 'string') {
    const v = val.toLowerCase()
    if (v.includes('pos') || v === '+') return 'positive'
    if (v.includes('neg') || v === '-') return 'negative'
    return 'neutral'
  }
  if (typeof val === 'number') {
    if (val > 0) return 'positive'
    if (val < 0) return 'negative'
    return 'neutral'
  }
  return 'neutral'
}

// Collapse long explanations so cards don't become too tall
const expanded = ref(false)
const maxChips = computed(() => (props.size === 'large' ? 6 : 4))

const featureChips = computed(() => {
  const items = props.recommendation.explanation?.features || []
  return expanded.value ? items : items.slice(0, maxChips.value)
})

const referenceChips = computed(() => {
  const items = props.recommendation.explanation?.references || []
  return expanded.value ? items : items.slice(0, maxChips.value)
})

const hasMoreFeatures = computed(
  () => (props.recommendation.explanation?.features?.length || 0) > maxChips.value,
)
const hasMoreReferences = computed(
  () => (props.recommendation.explanation?.references?.length || 0) > maxChips.value,
)
</script>

<template>
  <div :class="`recommendation-card-${props.size} card`">
    <div class="media">
      <div class="game-image thumb">
        <img :src="props.recommendation.boardgame.image_url" alt="Game image" />
      </div>
    </div>
    <div class="content">
      <div :class="`game-title-${props.size}`">
        <h2 class="title">{{ props.recommendation.boardgame.title }}</h2>
        <button
          v-if="props.size === 'large'"
          @click="toggleWishList"
          class="wishlist-button btn-outline"
          :aria-pressed="isInWishlist"
          :title="isInWishlist ? 'Remove from wishlist' : 'Add to wishlist'"
        >
          <Icon
            v-if="isInWishlist"
            icon="material-symbols:favorite-rounded"
            style="color: var(--color-danger)"
            width="22"
            height="22"
          />
          <Icon v-else icon="material-symbols:favorite-outline-rounded" width="22" height="22" />
        </button>
      </div>

      <div class="explanations">
        <template v-if="props.explanationStyle === 'features'">
          <div
            v-for="feature in featureChips"
            :key="feature.label"
            :class="`explanation-chip explanation-${normInfluence(feature.influence)} chip`"
          >
            {{ feature.label }}
          </div>
        </template>
        <template v-else-if="props.explanationStyle === 'references'">
          <div
            v-for="reference in referenceChips"
            :key="reference.bgg_id"
            :class="`explanation-chip explanation-${normInfluence(reference.influence)} chip`"
          >
            {{ reference.title }}
          </div>
        </template>
        <button
          v-if="(props.explanationStyle === 'features' && hasMoreFeatures) || (props.explanationStyle === 'references' && hasMoreReferences)"
          class="toggle-explanations"
          type="button"
          @click="expanded = !expanded"
        >
          {{ expanded ? 'Show less' : 'Show more' }}
        </button>
      </div>

      <div class="actions">
        <button class="btn-primary more-btn" @click="emit('viewgame', props.recommendation.boardgame.id)">
          <Icon icon="material-symbols:arrow-forward-rounded" width="20" height="20" />
          More information
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommendation-card-large {
  display: flex;
  flex-direction: row;
  width: 100%;
  padding: var(--space-4);
  margin: var(--space-4) 0;
  gap: var(--space-4);
  box-sizing: border-box;
}

.recommendation-card-small {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: var(--space-3);
  margin: var(--space-3) 0;
  gap: var(--space-3);
  box-sizing: border-box;
}

.wishlist-button,
.go-btn {
  cursor: pointer;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.game-title-large,
.game-title-small {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}

.title {
  font-size: var(--text-lg);
  margin: 0;
}

.explanations {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-1);
}

.explanation-chip { margin: 4px; }

.media { flex: 0 0 auto; }
.game-image {
  width: 148px;
  height: 148px;
}

.content {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.actions {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: var(--space-2);
}

.more-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-md);
}

/* Responsive adjustments for narrow screens */
@media (max-width: 520px) {
  .recommendation-card-large {
    flex-direction: column;
    padding: var(--space-3);
    gap: var(--space-3);
  }
  .media { width: 100%; }
  .game-image { width: 100%; height: 180px; }
  .actions { justify-content: flex-end; }
}
</style>

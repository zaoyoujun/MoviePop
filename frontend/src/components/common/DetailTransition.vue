<template>
  <Teleport to="body">
    <div v-if="transitionState.isActive" class="transition-overlay" :class="`overlay-${transitionState.phase}`">
      <div
        ref="transitionEl"
        class="transition-card"
        :class="`card-${transitionState.phase}`"
        :style="cardStyle"
      >
        <img :src="transitionState.imageSrc" alt="transition" class="transition-image" />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useDetailTransition } from '@/composables/useDetailTransition'

const router = useRouter()
const { transitionState, setPhase, completeTransition } = useDetailTransition()

const transitionEl = ref(null)

const CARD_RATIO = 268 / 178

const cardStyle = computed(() => {
  const { startRect, phase } = transitionState.value
  
  if (!startRect) return {}

  if (phase === 'start') {
    return {
      position: 'fixed',
      top: `${startRect.top}px`,
      left: `${startRect.left}px`,
      width: `${startRect.width}px`,
      height: `${startRect.height}px`,
      borderRadius: '10px'
    }
  }

  if (phase === 'center') {
    const centerX = window.innerWidth / 2
    const centerY = window.innerHeight / 2
    const targetWidth = Math.min(window.innerWidth * 0.6, 320)
    const targetHeight = targetWidth * CARD_RATIO
    const targetLeft = centerX - targetWidth / 2
    const targetTop = centerY - targetHeight / 2

    return {
      position: 'fixed',
      top: `${targetTop}px`,
      left: `${targetLeft}px`,
      width: `${targetWidth}px`,
      height: `${targetHeight}px`,
      borderRadius: '16px'
    }
  }

  if (phase === 'expand') {
    return {
      position: 'fixed',
      top: '0px',
      left: '0px',
      width: `${window.innerWidth}px`,
      height: `${window.innerHeight}px`,
      borderRadius: '0px'
    }
  }

  return {}
})

watch(
  () => transitionState.value.isActive,
  async (isActive) => {
    if (isActive) {
      document.body.style.overflow = 'hidden'
      
      await nextTick()
      
      setTimeout(() => {
        setPhase('center')
      }, 50)

      setTimeout(() => {
        setPhase('expand')
      }, 750)

      setTimeout(() => {
        router.push({ name: 'MovieDetail', params: { id: transitionState.value.movieId } })
        setPhase('fade')
      }, 1300)

      setTimeout(() => {
        completeTransition()
        document.body.style.overflow = ''
      }, 1600)
    } else {
      document.body.style.overflow = ''
    }
  }
)
</script>

<style scoped>
.transition-overlay {
  position: fixed;
  inset: 0;
  background: rgba(3, 5, 6, 0);
  z-index: 9998;
  transition: background 0.5s ease;
}

.transition-overlay.overlay-center,
.transition-overlay.overlay-expand {
  background: rgba(3, 5, 6, 0.95);
}

.transition-overlay.overlay-fade {
  background: rgba(3, 5, 6, 0);
}

.transition-card {
  z-index: 9999;
  overflow: hidden;
  transition:
    top 0.65s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    left 0.65s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    width 0.65s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    height 0.65s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    border-radius 0.65s cubic-bezier(0.25, 0.46, 0.45, 0.94),
    opacity 0.3s ease;
}

.transition-card.card-start {
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.28);
}

.transition-card.card-center {
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6);
}

.transition-card.card-expand {
  box-shadow: none;
}

.transition-card.card-fade {
  opacity: 0;
}

.transition-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>

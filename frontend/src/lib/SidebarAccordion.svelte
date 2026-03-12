<script>
  let { title, open = $bindable(false), children } = $props()
</script>

<div class="accordion">
  <button class="accordion-header" onclick={() => open = !open}>
    <span class="accordion-title">{title}</span>
    <span class="accordion-chevron" class:open>{@html '&#9662;'}</span>
  </button>
  {#if open}
    <div class="accordion-body">
      {@render children()}
    </div>
  {/if}
</div>

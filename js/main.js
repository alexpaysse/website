/* =========================================
   [BLANK] GOLF — Main JavaScript
   ========================================= */

'use strict';

/* =========================================
   Cart State Management
   ========================================= */
const Cart = {
  STORAGE_KEY: 'blank_golf_cart',

  get() {
    try {
      const data = localStorage.getItem(this.STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      return [];
    }
  },

  save(items) {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.warn('Could not save cart to localStorage');
    }
  },

  add(product) {
    const items = this.get();
    // product: { id, name, price, size, color, quantity, category }
    const existingIndex = items.findIndex(
      item => item.id === product.id && item.size === product.size && item.color === product.color
    );

    if (existingIndex > -1) {
      items[existingIndex].quantity += product.quantity || 1;
    } else {
      items.push({ ...product, quantity: product.quantity || 1 });
    }

    this.save(items);
    this.updateBadge();
    return items;
  },

  remove(id, size, color) {
    const items = this.get().filter(
      item => !(item.id === id && item.size === size && item.color === color)
    );
    this.save(items);
    this.updateBadge();
    return items;
  },

  updateQuantity(id, size, color, quantity) {
    const items = this.get();
    const idx = items.findIndex(
      item => item.id === id && item.size === size && item.color === color
    );
    if (idx > -1) {
      if (quantity <= 0) {
        return this.remove(id, size, color);
      }
      items[idx].quantity = quantity;
      this.save(items);
      this.updateBadge();
    }
    return items;
  },

  getCount() {
    return this.get().reduce((total, item) => total + item.quantity, 0);
  },

  getSubtotal() {
    return this.get().reduce((total, item) => total + (item.price * item.quantity), 0);
  },

  updateBadge() {
    const badges = document.querySelectorAll('.cart-badge');
    const count = this.getCount();
    badges.forEach(badge => {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.toggle('visible', count > 0);
    });
  },

  clear() {
    this.save([]);
    this.updateBadge();
  }
};

/* =========================================
   Toast Notifications
   ========================================= */
const Toast = {
  el: null,
  timer: null,

  init() {
    this.el = document.getElementById('toast');
    if (!this.el) {
      this.el = document.createElement('div');
      this.el.id = 'toast';
      this.el.className = 'toast';
      this.el.setAttribute('role', 'alert');
      this.el.setAttribute('aria-live', 'polite');
      document.body.appendChild(this.el);
    }
  },

  show(message, duration = 2800) {
    if (!this.el) this.init();
    this.el.textContent = message;
    this.el.classList.add('show');
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.el.classList.remove('show');
    }, duration);
  }
};

/* =========================================
   Navigation
   ========================================= */
function initNav() {
  // Sticky nav border on scroll
  const nav = document.querySelector('.nav');
  if (nav) {
    const handleScroll = () => {
      nav.classList.toggle('scrolled', window.scrollY > 10);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
  }

  // Mobile toggle
  const toggle = document.querySelector('.nav__mobile-toggle');
  const links = document.querySelector('.nav__links');
  if (toggle && links) {
    toggle.addEventListener('click', () => {
      const open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open);
      toggle.querySelectorAll('span').forEach((span, i) => {
        if (open) {
          if (i === 0) span.style.transform = 'rotate(45deg) translate(5px, 5px)';
          if (i === 1) span.style.opacity = '0';
          if (i === 2) span.style.transform = 'rotate(-45deg) translate(5px, -5px)';
        } else {
          span.style.transform = '';
          span.style.opacity = '';
        }
      });
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!nav?.contains(e.target) && links.classList.contains('open')) {
        links.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.querySelectorAll('span').forEach(span => {
          span.style.transform = '';
          span.style.opacity = '';
        });
      }
    });
  }

  // Set active nav link
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav__link').forEach(link => {
    const href = link.getAttribute('href');
    if (href === currentPage || (currentPage === '' && href === 'index.html')) {
      link.classList.add('active');
    }
  });

  // Init cart badge
  Cart.updateBadge();
}

/* =========================================
   Scroll Fade-in Animation
   ========================================= */
function initScrollAnimations() {
  const elements = document.querySelectorAll('.fade-in');
  if (!elements.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

  elements.forEach(el => observer.observe(el));
}

/* =========================================
   Shop Page — Filter Tabs
   ========================================= */
function initFilters() {
  const filterBtns = document.querySelectorAll('.filter-btn');
  const productCards = document.querySelectorAll('.shop-product-card');
  if (!filterBtns.length) return;

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      // Update active state
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const filter = btn.dataset.filter;

      productCards.forEach(card => {
        const category = card.dataset.category;
        if (filter === 'all' || category === filter) {
          card.classList.remove('hidden');
          // Stagger reveal
          const idx = [...productCards].filter(c => !c.classList.contains('hidden')).indexOf(card);
          card.style.transitionDelay = `${idx * 0.04}s`;
        } else {
          card.classList.add('hidden');
          card.style.transitionDelay = '0s';
        }
      });
    });
  });
}

/* =========================================
   Shop / Homepage — Add to Cart
   ========================================= */
function initAddToCart() {
  // Quick add buttons on product cards
  document.querySelectorAll('[data-add-to-cart]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();

      const productData = {
        id: btn.dataset.productId,
        name: btn.dataset.productName,
        price: parseFloat(btn.dataset.productPrice),
        category: btn.dataset.productCategory || '',
        size: btn.dataset.productSize || 'M',
        color: btn.dataset.productColor || 'Black',
        quantity: 1
      };

      Cart.add(productData);
      Toast.show(`${productData.name} added to cart`);
      animateCartBadge();
    });
  });
}

function animateCartBadge() {
  const badge = document.querySelector('.cart-badge');
  if (!badge) return;
  badge.style.transform = 'scale(1.5)';
  setTimeout(() => {
    badge.style.transform = '';
  }, 200);
}

/* =========================================
   Product Detail Page
   ========================================= */
function initProductDetail() {
  const page = document.querySelector('.product-detail');
  if (!page) return;

  // Size selector
  const sizeBtns = document.querySelectorAll('.size-btn:not(.unavailable)');
  let selectedSize = null;

  sizeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      sizeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedSize = btn.dataset.size;
      updateSizeLabel();
    });
  });

  function updateSizeLabel() {
    const label = document.querySelector('.selected-size-label');
    if (label) label.textContent = selectedSize || 'Select a size';
  }

  // Color selector
  const colorBtns = document.querySelectorAll('.color-btn');
  let selectedColor = 'Black';

  // Set first color active by default
  if (colorBtns.length) {
    colorBtns[0].classList.add('active');
    selectedColor = colorBtns[0].dataset.color;
  }

  colorBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      colorBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedColor = btn.dataset.color;
    });
  });

  // Quantity control
  const qtyValue = document.querySelector('.qty-value');
  const qtyMinus = document.querySelector('.qty-btn--minus');
  const qtyPlus = document.querySelector('.qty-btn--plus');
  let quantity = 1;

  if (qtyMinus && qtyPlus && qtyValue) {
    qtyMinus.addEventListener('click', () => {
      if (quantity > 1) {
        quantity--;
        qtyValue.value = quantity;
      }
    });
    qtyPlus.addEventListener('click', () => {
      if (quantity < 10) {
        quantity++;
        qtyValue.value = quantity;
      }
    });
    qtyValue.addEventListener('change', () => {
      quantity = Math.max(1, Math.min(10, parseInt(qtyValue.value) || 1));
      qtyValue.value = quantity;
    });
  }

  // Add to cart button
  const addBtn = document.querySelector('.product-detail__add');
  if (addBtn) {
    addBtn.addEventListener('click', () => {
      if (!selectedSize) {
        // Highlight size selector
        const sizeSection = document.querySelector('.size-grid');
        if (sizeSection) {
          sizeSection.style.animation = 'none';
          sizeSection.offsetHeight; // reflow
          sizeSection.style.animation = 'shake 0.3s ease';
        }
        Toast.show('Please select a size');
        return;
      }

      const productName = document.querySelector('.product-detail__name')?.textContent || 'Product';
      const priceText = document.querySelector('.product-detail__price')?.textContent || '$0';
      const price = parseFloat(priceText.replace(/[^0-9.]/g, ''));

      Cart.add({
        id: 'blank-polo',
        name: productName,
        price,
        size: selectedSize,
        color: selectedColor,
        category: 'tops',
        quantity
      });

      Toast.show(`${productName} (${selectedSize}, ${selectedColor}) added to cart`);
      animateCartBadge();
    });
  }

  // Accordion
  const accordionItems = document.querySelectorAll('.accordion-item');
  accordionItems.forEach(item => {
    const trigger = item.querySelector('.accordion-trigger');
    trigger?.addEventListener('click', () => {
      const isOpen = item.classList.contains('open');
      accordionItems.forEach(i => i.classList.remove('open'));
      if (!isOpen) item.classList.add('open');
    });
  });

  // Thumbnail gallery mock
  const thumbs = document.querySelectorAll('.product-thumb');
  thumbs.forEach(thumb => {
    thumb.addEventListener('click', () => {
      thumbs.forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
    });
  });
}

/* =========================================
   Cart Page
   ========================================= */
function initCartPage() {
  const cartPage = document.querySelector('.cart-page');
  if (!cartPage) return;

  renderCart();
}

function renderCart() {
  const items = Cart.get();
  const cartItemsContainer = document.querySelector('.cart-items');
  const cartEmptyEl = document.querySelector('.cart-empty');
  const cartContentEl = document.querySelector('.cart-content');
  const cartPageTitle = document.querySelector('.cart-page__title');

  if (!cartItemsContainer) return;

  if (items.length === 0) {
    // Show empty state
    if (cartContentEl) cartContentEl.style.display = 'none';
    if (cartEmptyEl) cartEmptyEl.style.display = 'flex';
    if (cartPageTitle) cartPageTitle.textContent = 'YOUR CART';
    return;
  }

  if (cartContentEl) cartContentEl.style.display = '';
  if (cartEmptyEl) cartEmptyEl.style.display = 'none';
  if (cartPageTitle) cartPageTitle.textContent = `YOUR CART (${Cart.getCount()})`;

  // Render items
  cartItemsContainer.innerHTML = items.map(item => `
    <article class="cart-item" data-id="${escHtml(item.id)}" data-size="${escHtml(item.size)}" data-color="${escHtml(item.color)}">
      <div class="cart-item__image" aria-hidden="true">
        ${bracketSVG(32)}
      </div>
      <div class="cart-item__details">
        <p class="cart-item__name">${escHtml(item.name)}</p>
        <p class="cart-item__meta">Size: ${escHtml(item.size)} &nbsp;|&nbsp; ${escHtml(item.color)}</p>
        <div class="cart-item__qty" role="group" aria-label="Quantity">
          <button class="cart-item__qty-btn" data-action="decrement" aria-label="Decrease quantity">−</button>
          <span class="cart-item__qty-num" aria-live="polite">${item.quantity}</span>
          <button class="cart-item__qty-btn" data-action="increment" aria-label="Increase quantity">+</button>
        </div>
      </div>
      <div class="cart-item__right">
        <span class="cart-item__price">$${(item.price * item.quantity).toFixed(2)}</span>
        <button class="cart-item__remove" data-action="remove" aria-label="Remove ${escHtml(item.name)} from cart">Remove</button>
      </div>
    </article>
  `).join('');

  // Bind cart item actions
  cartItemsContainer.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const cartItem = e.target.closest('.cart-item');
      const id = cartItem.dataset.id;
      const size = cartItem.dataset.size;
      const color = cartItem.dataset.color;
      const action = btn.dataset.action;

      if (action === 'remove') {
        Cart.remove(id, size, color);
        renderCart();
        updateOrderSummary();
        Toast.show('Item removed from cart');
      } else if (action === 'increment') {
        const items = Cart.get();
        const item = items.find(i => i.id === id && i.size === size && i.color === color);
        if (item) {
          Cart.updateQuantity(id, size, color, item.quantity + 1);
          renderCart();
          updateOrderSummary();
        }
      } else if (action === 'decrement') {
        const items = Cart.get();
        const item = items.find(i => i.id === id && i.size === size && i.color === color);
        if (item) {
          if (item.quantity <= 1) {
            Cart.remove(id, size, color);
            Toast.show('Item removed from cart');
          } else {
            Cart.updateQuantity(id, size, color, item.quantity - 1);
          }
          renderCart();
          updateOrderSummary();
        }
      }
    });
  });

  updateOrderSummary();
}

function updateOrderSummary() {
  const subtotal = Cart.getSubtotal();
  const freeShippingThreshold = 100;
  const shipping = subtotal >= freeShippingThreshold || subtotal === 0 ? 0 : 8;
  const total = subtotal + shipping;

  const subtotalEl = document.querySelector('.summary-subtotal');
  const shippingEl = document.querySelector('.summary-shipping');
  const totalEl = document.querySelector('.summary-total');
  const shippingNote = document.querySelector('.order-summary__shipping-note');

  if (subtotalEl) subtotalEl.textContent = `$${subtotal.toFixed(2)}`;
  if (shippingEl) shippingEl.textContent = shipping === 0 ? 'FREE' : `$${shipping.toFixed(2)}`;
  if (totalEl) totalEl.textContent = `$${total.toFixed(2)}`;

  if (shippingNote) {
    if (subtotal > 0 && subtotal < freeShippingThreshold) {
      const remaining = (freeShippingThreshold - subtotal).toFixed(2);
      shippingNote.textContent = `Add $${remaining} more for free shipping`;
    } else if (subtotal >= freeShippingThreshold) {
      shippingNote.textContent = 'You qualify for free shipping!';
    } else {
      shippingNote.textContent = 'Free shipping on orders over $100';
    }
  }
}

/* =========================================
   Checkout Button
   ========================================= */
function initCheckout() {
  const checkoutBtn = document.querySelector('.checkout-btn');
  if (!checkoutBtn) return;
  checkoutBtn.addEventListener('click', () => {
    if (Cart.getCount() === 0) {
      Toast.show('Your cart is empty');
      return;
    }
    Toast.show('Checkout coming soon — this is a demo store');
  });
}

/* =========================================
   Helpers
   ========================================= */
function escHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

function bracketSVG(size = 48) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <rect x="6" y="6" width="10" height="36" rx="0" stroke="currentColor" stroke-width="3.5" fill="none" stroke-linecap="square"/>
    <line x1="6" y1="6" x2="16" y2="6" stroke="currentColor" stroke-width="3.5"/>
    <line x1="6" y1="42" x2="16" y2="42" stroke="currentColor" stroke-width="3.5"/>
    <rect x="32" y="6" width="10" height="36" rx="0" stroke="currentColor" stroke-width="3.5" fill="none" stroke-linecap="square"/>
    <line x1="32" y1="6" x2="42" y2="6" stroke="currentColor" stroke-width="3.5"/>
    <line x1="32" y1="42" x2="42" y2="42" stroke="currentColor" stroke-width="3.5"/>
  </svg>`;
}

/* =========================================
   Keyframe injection for shake animation
   ========================================= */
function injectKeyframes() {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      20%, 60% { transform: translateX(-6px); }
      40%, 80% { transform: translateX(6px); }
    }
  `;
  document.head.appendChild(style);
}

/* =========================================
   Init
   ========================================= */
document.addEventListener('DOMContentLoaded', () => {
  Toast.init();
  injectKeyframes();
  initNav();
  initScrollAnimations();
  initFilters();
  initAddToCart();
  initProductDetail();
  initCartPage();
  initCheckout();
});

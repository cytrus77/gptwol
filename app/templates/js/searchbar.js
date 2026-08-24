let currentGroupFilter = 'all';

function filterComputers() {
  const query = document.querySelector('.search-input').value.toLowerCase();
  const cards = document.querySelectorAll('.computer-card');

  cards.forEach(card => {
    const title = card.querySelector('.title-sortable .sortable').textContent.toLowerCase();
    const infoText = card.querySelector('.info-sortable').textContent.toLowerCase();
    const cardGroup = (card.getAttribute('data-group') || '').toLowerCase();

    const matchesQuery = !query || title.includes(query) || infoText.includes(query) || cardGroup.includes(query);
    const matchesGroup = (currentGroupFilter === 'all') || (cardGroup === currentGroupFilter.toLowerCase());

    if (matchesQuery && matchesGroup) {
      card.classList.remove('hidden'); // Show card
    } else {
      card.classList.add('hidden'); // Hide card
    }
  });
}

function filterByGroup(groupName, event) {
  if (event) {
    event.preventDefault();
  }
  currentGroupFilter = groupName;

  const groupLabel = document.getElementById('selectedGroupFilterText');
  if (groupLabel) {
    groupLabel.textContent = groupName === 'all' ? 'All Groups' : groupName;
  }

  const items = document.querySelectorAll('#groupFilterMenu .dropdown-item');
  items.forEach(item => {
    item.classList.remove('active');
    if (item.textContent.trim() === (groupName === 'all' ? 'All Groups' : groupName)) {
      item.classList.add('active');
    }
  });

  filterComputers();
}

function clearSearchInput() {
  const searchInput = document.querySelector('.search-input');
  searchInput.value = '';
  filterComputers(); // Reset the filter
}

function ipToNumber(ip) {
  return ip.split('.').reduce((acc, octet) => (acc << 8) + Number(octet), 0);
}

function sortComputers(criteria) {
  const cardsContainer = document.querySelector('.row.row-sortable');
  const cards = Array.from(cardsContainer.children); // Convert NodeList to Array

  // Update the active class in the dropdown
  const dropdownItems = document.querySelectorAll('.dropdown-menu .dropdown-item');

  cards.sort((a, b) => {
    let aValue, bValue;

    switch (criteria) {
      case 'name':
        aValue = a.querySelector('.title-sortable .sortable').textContent.toLowerCase();
        bValue = b.querySelector('.title-sortable .sortable').textContent.toLowerCase();
        return aValue.localeCompare(bValue);

      case 'group':
        aValue = (a.getAttribute('data-group') || '').toLowerCase();
        bValue = (b.getAttribute('data-group') || '').toLowerCase();
        return aValue.localeCompare(bValue);

      case 'ip':
        const aIp = a.querySelector('.info-sortable .sortable:nth-of-type(1)').textContent;
        const bIp = b.querySelector('.info-sortable .sortable:nth-of-type(1)').textContent;
        return ipToNumber(aIp) - ipToNumber(bIp);

      case 'mac':
        aValue = a.querySelector('.info-sortable .sortable:nth-of-type(2)').textContent.toLowerCase();
        bValue = b.querySelector('.info-sortable .sortable:nth-of-type(2)').textContent.toLowerCase();
        return aValue.localeCompare(bValue);
    }
  });

  // Clear the current cards and append sorted cards
  cardsContainer.innerHTML = '';
  cards.forEach(card => cardsContainer.appendChild(card));
}

// Attach the filter function to the input event
document.querySelector('.search-input').addEventListener('input', filterComputers);

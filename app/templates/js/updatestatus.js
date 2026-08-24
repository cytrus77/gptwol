// ---
// Status Indicator Batch & Single Updating
window.addEventListener('load', function() {
  updateAllStatuses();
});

function applyStatus(element, buttonElement, status) {
  if (status === 'awake') {
    element.classList.remove('asleep');
    element.classList.add('awake');
    buttonElement.classList.remove('btn-success');
    buttonElement.classList.add('btn-danger');
    buttonElement.title = 'Sleep';
  } else {
    element.classList.remove('awake');
    element.classList.add('asleep');
    buttonElement.classList.remove('btn-danger');
    buttonElement.classList.add('btn-success');
    buttonElement.title = 'Wake';
  }
}

function updateAllStatuses() {
  if (typeof check_all_statuses_url !== 'undefined') {
    fetch(`${check_all_statuses_url}`)
      .then(response => response.json())
      .then(data => {
        const statusIndicators = document.querySelectorAll('.status-indicator');
        statusIndicators.forEach(function(indicator) {
          const card = indicator.closest('.card');
          if (!card) return;
          const editBtn = card.querySelector('[data-mac-address]');
          const mac = editBtn ? editBtn.getAttribute('data-mac-address') : '';
          const buttonElement = card.querySelector('.status-power');

          if (mac && data[mac]) {
            applyStatus(indicator, buttonElement, data[mac]);
          }
        });
      })
      .catch(err => {
        fallbackIndividualUpdates();
      });
  } else {
    fallbackIndividualUpdates();
  }
}

function fallbackIndividualUpdates() {
  const statusIndicators = document.querySelectorAll('.status-indicator');
  statusIndicators.forEach(function(indicator) {
    const ip_address = indicator.getAttribute('data-ip-address');
    const test_type = indicator.getAttribute('data-test-type');
    const buttonElement = indicator.closest('.card').querySelector('.status-power');
    updateStatus(ip_address, test_type, indicator, buttonElement);
  });
}

function updateStatus(ip_address, test_type, element, buttonElement) {
  fetch(`${check_status_url}?ip_address=${ip_address}&test_type=${test_type}`)
    .then(response => response.text())
    .then(status => {
      applyStatus(element, buttonElement, status);
    });
}

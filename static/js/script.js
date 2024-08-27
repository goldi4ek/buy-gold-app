document.addEventListener("DOMContentLoaded", () => {
  const buyButton = document.querySelector(".buy");
  const sellButton = document.querySelector(".sell");
  const inputValue = document.querySelector(".input-value");
  const goldBalance = document.querySelector(".gold-balance");
  const silverBalance = document.querySelector(".silver-balance");
  const goldPrice = document.querySelector(".gold-price");

  const tg = window.Telegram.WebApp;
  var userId;
  try {
    userId = tg.initDataUnsafe.user.id;
  } catch {
    document.body.innerHTML =
      "<h1 style='color:white'>Цей додаток доступний лише через Telegram WebApp</h1>";
    return;
  }

  tg.setHeaderColor("#13005a");
  tg.expand();

  inputValue.addEventListener("keypress", function (evt) {
    if (
      evt.which != 8 &&
      evt.which != 0 &&
      evt.which != 46 &&
      (evt.which < 48 || evt.which > 57)
    ) {
      evt.preventDefault();
    }
  });

  const updateBalances = (newSilver, newGold, newPrice) => {
    silverBalance.textContent = newSilver;
    goldBalance.textContent = newGold;
    goldPrice.textContent = newPrice;
  };

  buyButton.addEventListener("click", async () => {
    const amount = parseFloat(inputValue.value);
    if (amount > 0) {
      const response = await fetch(`buy_gold/${userId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          amount: amount,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        updateBalances(
          result["new_silver"],
          result["new_gold"],
          result["new_price"]
        );
      } else {
        const errorData = await response.json();
        tg.showAlert(errorData.detail);
      }
    } else {
      tg.showAlert("Invalid amount");
    }
  });

  sellButton.addEventListener("click", async () => {
    const amount = parseFloat(inputValue.value);
    if (amount > 0) {
      const response = await fetch(`sell_gold/${userId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          amount: amount,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        updateBalances(
          result["new_silver"],
          result["new_gold"],
          result["new_price"]
        );
      } else {
        const errorData = await response.json();
        tg.showAlert(errorData.detail);
      }
    } else {
      tg.showAlert("Invalid amount");
    }
  });

  /* const tg = window.Telegram.Webapp; */
  /* const userId = tg.initDataUnsafe.user.id; */
});

# Türkçe Proje Açıklaması

Bu repo, phishing URL tespiti için veri üretiminden model değerlendirmesine kadar tüm çalışma akışını içerir. Konferans makalesi veri üretimi, klasik makine öğrenmesi, ensemble öğrenme ve XAI bölümlerini kapsamaktadır. Character CNN, Stacked Character BiLSTM ve CNN-BiLSTM deneyleri ise bitirme projesine daha sonra eklenmiştir.

## Temel sonuçlar

- En başarılı temel ML modeli: **LightGBM**, F1 = 0.9840
- En başarılı ensemble modeli: **Stacking AllBase**, F1 = 0.9861
- En başarılı DL modeli: **CNN-BiLSTM Seed Ensemble**, F1 = 0.9807
- SHAP ve permutation importance korelasyonu: **0.916**

Notebook’lar 01’den 08’e kadar sırayla çalıştırılmalıdır. Orijinal kodlar Windows ve Kaggle ortamlarında geliştirildiği için bazı veri yollarının yerel ortama göre değiştirilmesi gerekir. Ayrıntılar için `reproducibility.md` dosyasına bakın.

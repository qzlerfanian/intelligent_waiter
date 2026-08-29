from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("orders", "0003_order_confirmation")]
    operations = [
        migrations.AddField(model_name="order", name="discount_total", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="order", name="promotion_code", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="order", name="fulfillment_type", field=models.CharField(choices=[("dine_in", "Dine in"), ("takeaway", "Takeaway"), ("delivery", "Delivery")], default="dine_in", max_length=16)),
        migrations.AddField(model_name="order", name="delivery_address", field=models.TextField(blank=True)),
    ]
